import errno
import json
from pathlib import Path

import eccodes
import pytest
import xarray as xr
from cedarkit_query import ErrorValue, QueryError, Request, SourceError
from click.testing import CliRunner

from reki import from_source
from reki.cli import EXIT_NO_MATCH, cli
from reki.diagnostics import collect_io_metrics


def _write(path):
    with path.open("wb") as output:
        for level in (850, 500):
            message = eccodes.codes_grib_new_from_samples("GRIB2")
            try:
                eccodes.codes_set(message, "shortName", "t")
                eccodes.codes_set(message, "typeOfLevel", "isobaricInhPa")
                eccodes.codes_set(message, "level", level)
                eccodes.codes_write(message, output)
            finally:
                eccodes.codes_release(message)


def test_inspect_and_ls_json_use_public_metadata_api(tmp_path):
    path = tmp_path / "fields.grib"
    _write(path)
    runner = CliRunner()

    with collect_io_metrics() as metrics:
        result = runner.invoke(cli, ["inspect", str(path), "--no-index", "--json"])
        assert result.exit_code == 0, result.output
        inspect = json.loads(result.output)
        assert inspect["summary"]["field_count"] == 2
        assert inspect["capabilities"]["metadata"] is True
        assert metrics.snapshot()["value_decode_count"] == 0

    result = runner.invoke(cli, [
        "ls", str(path), "--parameter", "t", "--level-type", "pl", "--level", "850",
        "--keys", "index,level", "--no-index", "--json",
    ])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == [{"index": 0, "level": 850.0}]


def test_query_is_bounded_and_has_a_no_match_exit_code(tmp_path):
    path = tmp_path / "fields.grib"
    _write(path)
    runner = CliRunner()

    result = runner.invoke(cli, [
        "query", str(path), "--level", "100", "--no-index", "--json",
    ])
    assert result.exit_code == EXIT_NO_MATCH
    assert json.loads(result.output) == []

    duplicate = runner.invoke(cli, ["ls", str(path), "--keys", "level,level"])
    assert duplicate.exit_code == 2
    conflict = runner.invoke(cli, ["inspect", str(path), "--use-index", "--refresh-index"])
    assert conflict.exit_code == 2


def test_retired_cli_index_is_rejected_without_io(tmp_path):
    path = tmp_path / "fields.grib"
    index_dir = tmp_path / "indexes"
    _write(path)
    runner = CliRunner()

    default = runner.invoke(cli, ["inspect", str(path), "--index-dir", str(index_dir), "--json"])
    assert default.exit_code == 0, default.output
    assert not index_dir.exists()

    enabled = runner.invoke(cli, ["inspect", str(path), "--use-index", "--index-dir", str(index_dir), "--json"])
    assert enabled.exit_code == 4 and "unsupported" in enabled.output
    assert not index_dir.exists()


def test_catalog_commands_remain_available():
    result = CliRunner().invoke(cli, ["catalog", "--help"])
    assert result.exit_code == 0
    assert "show" in result.output and "list" in result.output


def test_native_request_cli_can_explain_and_read(tmp_path):
    path = tmp_path / "fields.grib"
    _write(path)
    request = tmp_path / "request.json"
    request.write_text(json.dumps({
        "api_version": "cedarkit.request/v1",
        "source": {"kind": "file", "path": path.name},
        "queries": [{"native": {"grib": {"parameterNumber": 0}}, "level": 850}],
    }))
    runner = CliRunner()
    result = runner.invoke(cli, ["request", "explain", str(request)])
    assert result.exit_code == 0, result.output
    assert len(json.loads(result.output)["effective_queries"]) == 1
    listed = runner.invoke(cli, ["request", "list", str(request)])
    assert listed.exit_code == 0 and listed.stderr == ""
    out = tmp_path / "raw.nc"
    result = runner.invoke(cli, ["request", "read", str(request), str(out)])
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert out.is_file() and report["overall"]["field_count"] == 1
    assert report == json.loads(listed.stdout)


@pytest.fixture
def native_request(tmp_path):
    source = tmp_path / "fields.grib"
    _write(source)
    return {
        "api_version": "cedarkit.request/v1",
        "source": {"kind": "file", "path": source.name},
        "queries": [{"native": {"grib": {"parameterNumber": 0}}, "level": 850}],
    }


@pytest.mark.parametrize(
    ("action", "failure", "code"),
    [
        ("explain", "malformed_request", "invalid_request"),
        ("list", "missing_source", "resource_not_found"),
        ("list", "corrupt_source", "decode_failed"),
        ("read", "strict_completeness", "completeness_undetermined"),
    ],
)
def test_request_cli_serializes_public_errors(tmp_path, native_request, action, failure, code):
    path = tmp_path / "request.json"
    if failure == "missing_source":
        native_request["source"]["path"] = "missing.grib"
    elif failure == "corrupt_source":
        (tmp_path / native_request["source"]["path"]).write_bytes(b"not a GRIB file")
    elif failure == "strict_completeness":
        native_request["completeness"] = "required"
    path.write_text("{" if failure == "malformed_request" else json.dumps(native_request))

    with pytest.raises((QueryError, SourceError)) as caught:
        request = Request.load(path)
        with from_source(request.source, context=request.context) as source:
            source.sel(request.queries).all(completeness=request.completeness)

    output = tmp_path / "output.nc"
    args = ["request", action, str(path)]
    if action == "read":
        output.write_bytes(b"previous result")
        args.append(str(output))
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 1
    assert result.stdout == ""
    error = ErrorValue(json.loads(result.stderr))
    assert error.code == code and error.to_dict() == caught.value.to_dict()
    if action == "read":
        assert output.read_bytes() == b"previous result"


@pytest.mark.parametrize("existing_output", [False, True])
def test_request_cli_cleans_partial_netcdf_on_write_error(tmp_path, native_request, monkeypatch, existing_output):
    request = tmp_path / "request.json"
    request.write_text(json.dumps(native_request))
    output = tmp_path / "output.nc"
    if existing_output:
        output.write_bytes(b"previous result")
    before = set(tmp_path.iterdir())

    def fail_write(self, path):
        Path(path).write_bytes(b"partial file")
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(xr.Dataset, "to_netcdf", fail_write)
    result = CliRunner().invoke(cli, ["request", "read", str(request), str(output)])
    assert result.exit_code == 1
    assert result.stdout == ""
    error = ErrorValue(json.loads(result.stderr))
    assert (error.code, error.path) == ("io_error", "/output")
    assert error.context["resource"] == str(output)
    assert error.context["operation"] == "write_netcdf"
    assert set(tmp_path.iterdir()) == before
    if existing_output:
        assert output.read_bytes() == b"previous result"


def test_request_cli_usage_error_keeps_click_status():
    result = CliRunner().invoke(cli, ["request", "read"])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert "Missing argument 'INPUT_PATH'" in result.stderr
