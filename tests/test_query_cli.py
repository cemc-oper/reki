"""T14 CLI protocol, I/O separation, and local reference parity."""

import importlib.util
import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from cedarkit_query import Response, load_request
from reki.catalog import load_catalog
from reki.catalog.query_binding import CatalogSnapshot, plan_source_binding
from reki.cli import cli
from reki.diagnostics import collect_io_metrics
from reki.query_locator import locate_fields


@pytest.fixture(scope="module")
def assets(tmp_path_factory):
    script = Path(__file__).parent / "fixtures/t09/generate.py"
    spec = importlib.util.spec_from_file_location("t14_assets", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = tmp_path_factory.mktemp("t14-grib")
    module.build(root)
    return root


def _catalog(root, path):
    path.write_text("api_version: reki.catalog/v1\ndatasets:\n  - id: grid\n    source:\n"
                    "      name: file-pattern\n      args:\n"
                    f"        - {str(root / 'baseline')!r}\n"
                    "        - 'f{forecast_hour_label}_m1.grib2'\n")
    return path


def _request(action, *, output=None, level=85000, missing=None):
    value = {"api_version": "cedarkit.request/v1", "action": action,
             "query": {"api_version": "cedarkit.query/v1", "domain": "grid", "dataset": "grid",
                       "parameter": "cedarkit.t", "reference_time": "2026-08-30T00:00:00Z",
                       "lead_time": "PT24H", "vertical": {"type": "isobaric", "unit": "Pa", "values": level},
                       "statistic": {"kind": "instant"},
                       "member": {"id": "1", "role": "perturbation"}}}
    if output is not None:
        value["options"] = {"output": {"format": "netcdf", "path": str(output)}}
    if missing is not None:
        value["policy"] = {"missing": missing}
    return value


def _invoke(runner, catalog, action, request, *options):
    return runner.invoke(cli, ["request", "--catalog", str(catalog), "--native-parameter",
                               "cedarkit.t=t", "--member-role", "1=perturbation", *options,
                               action, "--input-format", "json"], input=json.dumps(request))


def test_validate_is_schema_only_and_accepts_text_and_yaml(monkeypatch):
    from reki import query_cli

    monkeypatch.setattr(query_cli, "_snapshot", lambda config: (_ for _ in ()).throw(
        AssertionError("validate opened catalog")))
    runner = CliRunner()
    text = "VALIDATE dataset=grid parameter=cedarkit.t"
    with collect_io_metrics() as metrics:
        result = runner.invoke(cli, ["request", "validate", "--input-format", "text"], input=text)
    assert result.exit_code == 0, result.output
    assert Response(json.loads(result.output)).status == "valid"
    assert metrics.snapshot()["file_open_count"] == 0
    yaml = "api_version: cedarkit.request/v1\naction: validate\nquery:\n  api_version: cedarkit.query/v1\n  domain: grid\n  dataset: grid\n"
    result = runner.invoke(cli, ["request", "validate", "--input-format", "yaml"], input=yaml)
    assert result.exit_code == 0, result.output
    assert Response(json.loads(result.output)).status == "valid"


def test_plan_uses_snapshot_and_never_scans_data(assets, tmp_path):
    catalog = _catalog(assets, tmp_path / "catalog.yaml")
    runner = CliRunner()
    with collect_io_metrics() as metrics:
        result = _invoke(runner, catalog, "plan", _request("plan"))
    assert result.exit_code == 0, result.output
    response = Response(json.loads(result.output))
    assert response.status == "planned"
    assert response.details["normalized_request"]["query"]["lead_time"] == "PT86400S"
    assert len(response.details["expanded_requests"]) == 1
    assert metrics.snapshot()["grib_header_scan_count"] == 0
    assert metrics.snapshot()["value_decode_count"] == 0


def test_json_yaml_and_text_plan_have_same_query_identity(assets, tmp_path):
    catalog = _catalog(assets, tmp_path / "catalog.yaml")
    request = _request("plan")
    runner = CliRunner()
    prefix = ["request", "--catalog", str(catalog), "plan", "--input-format"]
    json_result = runner.invoke(cli, [*prefix, "json"], input=json.dumps(request))
    yaml_result = runner.invoke(cli, [*prefix, "yaml"], input=yaml.safe_dump(request))
    text_result = runner.invoke(cli, [*prefix, "text"], input=(
        "PLAN dataset=grid parameter=cedarkit.t reference_time=2026-08-30T00:00:00Z "
        "lead_time=PT24H vertical.type=isobaric vertical.unit=Pa vertical.values=85000 "
        "statistic.kind=instant member=perturbation:1"))
    for result in (json_result, yaml_result, text_result):
        assert result.exit_code == 0, result.output
    assert len({json.loads(result.output)["query_id"] for result in
                (json_result, yaml_result, text_result)}) == 1


def test_list_locate_and_read_match_python_reference(assets, tmp_path):
    catalog = _catalog(assets, tmp_path / "catalog.yaml")
    runner = CliRunner()
    with collect_io_metrics() as list_metrics:
        listed = _invoke(runner, catalog, "list", _request("list"))
    assert listed.exit_code == 0, listed.output
    assert list_metrics.snapshot()["value_decode_count"] == 0
    fields = Response(json.loads(listed.output)).details["fields"]
    assert len(fields) == 2
    assert {field["metadata"]["level"] for field in fields} == {500.0, 850.0}

    with collect_io_metrics() as metrics:
        located = _invoke(runner, catalog, "locate", _request("locate"))
    assert located.exit_code == 0, located.output
    response = Response(json.loads(located.output))
    assert response.status == "available"
    assert response.details["items"][0]["verification"] == "field_confirmed"
    assert metrics.snapshot()["value_decode_count"] == 0
    snapshot = CatalogSnapshot(load_catalog(builtin=False, plugins=False, user=False, explicit=catalog),
                               response.catalog_version)
    plan = plan_source_binding(load_request(_request("locate")).query, snapshot=snapshot)
    direct = locate_fields(plan, native_parameters={"cedarkit.t": "t"},
                           member_roles={"1": "perturbation"}, index_policy="off")
    assert response.references[0] == direct.references[0].to_dict()

    output = tmp_path / "field.nc"
    with collect_io_metrics() as metrics:
        read = _invoke(runner, catalog, "read", _request("read", output=output))
    assert read.exit_code == 0, read.output
    data = Response(json.loads(read.output))
    assert data.status == "available" and data.artifact["path"] == str(output)
    assert data.references[0] == direct.references[0].to_dict()
    assert output.is_file()
    assert metrics.snapshot()["value_decode_count"] > 0
    import xarray as xr
    with xr.open_dataarray(output, engine="scipy") as array:
        assert array.attrs["units"] == "K"
        assert array.shape == (1, 1, 1, 3, 4)


def test_missing_and_bad_requests_have_stable_json_and_exit_codes(assets, tmp_path):
    catalog = _catalog(assets, tmp_path / "catalog.yaml")
    runner = CliRunner()
    missing = _invoke(runner, catalog, "locate", _request("locate", level=70000))
    assert missing.exit_code == 3
    assert Response(json.loads(missing.output)).error["code"] == "not_found"
    partial = _invoke(runner, catalog, "locate", _request("locate", level=70000, missing="partial"))
    assert partial.exit_code == 0, partial.output
    response = Response(json.loads(partial.output))
    assert response.status == "partial"
    assert response.details["items"][0]["verification"] == "path_exists"
    no_output = _invoke(runner, catalog, "read", _request("read"))
    assert no_output.exit_code == 2
    assert Response(json.loads(no_output.output)).error["path"] == "/options/output"
    wrong = _invoke(runner, catalog, "plan", _request("validate"))
    assert wrong.exit_code == 2
    assert Response(json.loads(wrong.output)).error["path"] == "/action"


def test_request_list_and_remote_availability_are_explicit():
    runner = CliRunner()
    lines = "VALIDATE dataset=a\n---\nVALIDATE dataset=b\n"
    result = runner.invoke(cli, ["request", "validate", "--input-format", "text"], input=lines)
    assert result.exit_code == 0, result.output
    responses = json.loads(result.output)
    assert len(responses) == 2
    assert all(Response(item).status == "valid" for item in responses)

    source = _request("locate")
    source["query"]["dataset"] = "cma_gfs_gmf_cmadaas"
    remote = runner.invoke(cli, ["request", "locate", "--input-format", "json"],
                           input=json.dumps(source))
    assert remote.exit_code == 0, remote.output
    response = Response(json.loads(remote.output))
    assert response.status == "unknown"
    assert response.details["items"][0]["verification"] == "remote_unverified"
    assert response.missing[0]["code"] == "availability_unknown"


def test_legacy_cli_commands_remain_available():
    runner = CliRunner()
    for command in ("inspect", "ls", "query", "catalog"):
        result = runner.invoke(cli, [command, "--help"])
        assert result.exit_code == 0, result.output
