"""T10 metadata-only location, availability, and reference validity."""

import importlib.util
import json
import os
import shutil
from pathlib import Path

import pytest

from cedarkit_query import QueryError, resource_identity
from reki.catalog import load_catalog
from reki.catalog.query_binding import CatalogSnapshot, plan_source_binding
from reki.diagnostics import collect_io_metrics
from reki.query_locator import list_fields, locate_fields, verify_data_reference


@pytest.fixture(scope="module")
def assets(tmp_path_factory):
    script = Path(__file__).resolve().parents[2] / "fixtures/t09/generate.py"
    spec = importlib.util.spec_from_file_location("t10_assets", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = tmp_path_factory.mktemp("t10-grib")
    module.build(root)
    return root


def _plan(root, *, lead="PT86400S", level=85000, member=None, source=None, dataset="grid",
          query_extra=None):
    source = source or {"name": "file-pattern", "args": [str(root / "baseline"), "f{forecast_hour_label}_m1.grib2"]}
    catalog = load_catalog(builtin=False, plugins=False, user=False, explicit={
        "api_version": "reki.catalog/v1", "datasets": [{"id": dataset, "source": source}]})
    query = {"api_version": "cedarkit.query/v1", "domain": "grid", "dataset": dataset,
             "parameter": "cedarkit.t", "reference_time": "2026-08-30T00:00:00Z",
             "lead_time": lead, "vertical": {"type": "isobaric", "unit": "Pa", "values": level},
             "statistic": {"kind": "instant"}}
    if member is not None:
        query["member"] = {"id": str(member), "role": "perturbation"}
    if query_extra:
        query.update(query_extra)
    return plan_source_binding(query, snapshot=CatalogSnapshot(catalog, "t10-catalog"))


def _locate(plan, **kwargs):
    return locate_fields(plan, native_parameters={"cedarkit.t": "t"},
                         member_roles={"1": "perturbation", "2": "perturbation"}, **kwargs)


def test_expanded_locator_confirms_fields_without_decoding_values(assets, tmp_path):
    plan = _plan(assets, lead=["PT0S", "PT86400S", "PT172800S"], member=1)
    with collect_io_metrics() as metrics:
        report = _locate(plan, index_dir=tmp_path / "index", index_policy="off")
    assert report.status == "available"
    assert len(report.references) == 3
    assert {item.verification for item in report.items} == {"field_confirmed"}
    assert all(item.reference.field_locator["offset"] >= 0 for item in report.items)
    assert metrics.snapshot()["grib_header_scan_count"] == 6
    assert metrics.snapshot()["value_decode_count"] == 0
    restored = verify_data_reference(json.dumps(report.references[0].to_dict()))
    assert restored == report.references[0]
    assert resource_identity(restored).startswith("sha256:")


def test_list_uses_metadata_only_and_retains_each_resource_path(assets, tmp_path):
    plan = _plan(assets, lead=["PT0S", "PT86400S"])
    with collect_io_metrics() as metrics:
        report = list_fields(plan, index_dir=tmp_path / "index", index_policy="off")
    assert report.status == "available"
    assert len(report.fields) == 4
    assert len({item.path for item in report.fields}) == 2
    assert all(item.fingerprint["size"] > 0 for item in report.fields)
    assert metrics.snapshot()["value_decode_count"] == 0


def test_hot_index_serves_repeated_location_without_header_scan(assets, tmp_path):
    plan = _plan(assets, member=1)
    index_dir = tmp_path / "index"
    _locate(plan, index_dir=index_dir)
    with collect_io_metrics() as metrics:
        report = _locate(plan, index_dir=index_dir)
    assert report.items[0].verification == "field_confirmed"
    assert metrics.snapshot()["index_hit_count"] >= 1
    assert metrics.snapshot()["grib_header_scan_count"] == 0
    assert metrics.snapshot()["value_decode_count"] == 0


def test_path_exists_is_distinct_from_field_confirmed_and_absent_path(assets):
    field_missing = _locate(_plan(assets, level=70000), missing="partial", index_policy="off")
    assert field_missing.items[0].verification == "path_exists"
    assert field_missing.references[0].verification == "path_exists"
    assert "field_locator" not in field_missing.references[0].to_dict()
    path_missing = _locate(_plan(assets, lead="PT280800S"), missing="partial")
    assert path_missing.items[0].verification == "not_found"
    assert path_missing.items[0].path.endswith("f078_m1.grib2")
    assert path_missing.references == ()
    with pytest.raises(QueryError) as caught:
        _locate(_plan(assets, level=70000), index_policy="off")
    assert caught.value.code == "not_found"
    assert caught.value.context["verification"] == "path_exists"


def test_remote_is_unverified_without_visiting_service():
    source = {"name": "cmadaas", "kwargs": {"kind": "model_grid", "data_code": "TEST_CODE"}}
    plan = _plan(Path("/unused"), source=source)
    with collect_io_metrics() as metrics:
        report = _locate(plan)
    assert report.status == "unknown"
    assert report.items[0].verification == "remote_unverified"
    assert report.references[0].resource["locator"] == "TEST_CODE"
    assert metrics.snapshot()["file_open_count"] == 0
    with pytest.raises(QueryError) as caught:
        verify_data_reference(report.references[0])
    assert caught.value.code == "availability_unknown"


def test_stale_reference_detects_file_replacement(assets, tmp_path):
    active = tmp_path / "active.grib2"
    shutil.copyfile(assets / "baseline/f042_m0.grib2", active)
    plan = _plan(tmp_path, lead="PT151200S", source={"name": "file-pattern",
                 "args": [str(tmp_path), "active.grib2"]})
    reference = _locate(plan, index_policy="off").references[0]
    replacement = tmp_path / "replacement.grib2"
    shutil.copyfile(assets / "cases/resource_updated.grib2", replacement)
    replacement.replace(active)
    with pytest.raises(QueryError) as caught:
        verify_data_reference(reference)
    assert caught.value.code == "stale_reference"


def test_relocation_rebuilds_stale_index_after_replacement(assets, tmp_path):
    active = tmp_path / "active.grib2"
    shutil.copyfile(assets / "baseline/f042_m0.grib2", active)
    plan = _plan(tmp_path, lead="PT151200S", source={"name": "file-pattern",
                 "args": [str(tmp_path), "active.grib2"]})
    index_dir = tmp_path / "index"
    old = _locate(plan, index_dir=index_dir).references[0]
    replacement = tmp_path / "replacement.grib2"
    shutil.copyfile(assets / "cases/resource_updated.grib2", replacement)
    replacement.replace(active)
    with collect_io_metrics() as metrics:
        new = _locate(plan, index_dir=index_dir).references[0]
    assert old.resource["fingerprint"] != new.resource["fingerprint"]
    assert resource_identity(old) != resource_identity(new)
    assert metrics.snapshot().index_miss_reasons.get("stale", 0) >= 1
    assert metrics.snapshot()["grib_header_scan_count"] == 2
    assert metrics.snapshot()["value_decode_count"] == 0


def test_unsupported_native_mapping_and_member_role_are_explicit(assets):
    plan = _plan(assets, member=1)
    with pytest.raises(QueryError) as caught:
        locate_fields(plan)
    assert caught.value.code == "unsupported"
    with pytest.raises(QueryError) as caught:
        locate_fields(plan, native_parameters={"cedarkit.t": "t"})
    assert caught.value.code == "unsupported"


def test_permission_error_has_distinct_code(assets, monkeypatch):
    def denied(_path):
        raise PermissionError("denied")
    monkeypatch.setattr("reki.query_locator.fingerprint_file", denied)
    with pytest.raises(QueryError) as caught:
        _locate(_plan(assets))
    assert caught.value.code == "permission_denied"


def test_duplicate_field_is_reported_as_multiple_matches(assets, tmp_path):
    target = tmp_path / "two.grib2"
    target.write_bytes((assets / "baseline/f024_m1.grib2").read_bytes()
                       + (assets / "cases/duplicate.grib2").read_bytes())
    plan = _plan(tmp_path, source={"name": "file-pattern", "args": [str(tmp_path), "two.grib2"]},
                 member=1)
    with pytest.raises(QueryError) as caught:
        _locate(plan, index_policy="off")
    assert caught.value.code == "multiple_matches"


def test_reki_local_requires_explicit_config_and_resolves_it(assets, tmp_path):
    config_dir = tmp_path / "config"
    config = config_dir / "od/example/grid.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("file_name: 'f024_m1.grib2'\npaths:\n"
                      f"  - level: archive\n    path: '{assets / 'baseline'}'\n")
    catalog = load_catalog(builtin=False, plugins=False, user=False, explicit={
        "api_version": "reki.catalog/v1", "datasets": [{"id": "grid", "source": {
            "name": "local", "args": ["example/grid"]}}]})
    query = _plan(assets).query
    plan = plan_source_binding(query, snapshot=CatalogSnapshot(catalog, "catalog-v1"),
                               local_config_version="config-v1")
    with pytest.raises(QueryError) as caught:
        _locate(plan)
    assert caught.value.code == "unsupported"
    assert _locate(plan, local_config_dir=config_dir, index_policy="off").items[0].verification == "field_confirmed"


def test_invalid_serialized_reference_is_rejected():
    with pytest.raises(QueryError) as caught:
        verify_data_reference("{")
    assert caught.value.code == "invalid_query"


def test_optional_sha256_detects_change_even_when_stat_tuple_is_restored(assets, tmp_path):
    active = tmp_path / "active.grib2"
    shutil.copyfile(assets / "baseline/f042_m0.grib2", active)
    plan = _plan(tmp_path, lead="PT151200S", source={"name": "file-pattern",
                 "args": [str(tmp_path), "active.grib2"]})
    reference = _locate(plan, index_policy="off", hash_resources=True).references[0]
    original = active.stat()
    with active.open("r+b") as stream:
        stream.seek(100)
        byte = stream.read(1)
        stream.seek(100)
        stream.write(bytes([byte[0] ^ 1]))
    os.utime(active, ns=(original.st_atime_ns, original.st_mtime_ns))
    assert active.stat().st_ino == original.st_ino
    assert active.stat().st_size == original.st_size
    assert active.stat().st_mtime_ns == original.st_mtime_ns
    with pytest.raises(QueryError) as caught:
        verify_data_reference(reference)
    assert caught.value.code == "stale_reference"


def test_statistic_is_checked_and_unverified_coverage_is_rejected(assets):
    accumulated = _plan(assets, query_extra={"statistic": {"kind": "accum", "window": "PT21600S"}})
    report = _locate(accumulated, missing="partial", index_policy="off")
    assert report.items[0].verification == "path_exists"
    covered = _plan(assets, query_extra={"coverage": {
        "crs": "EPSG:4326", "bbox": [100, 48, 103, 50], "relation": "intersects"}})
    with pytest.raises(QueryError) as caught:
        _locate(covered)
    assert caught.value.code == "unsupported"
