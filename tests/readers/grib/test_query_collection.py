"""T11 multi-resource organization against the generated T09 GRIB truth."""

import importlib.util
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cedarkit_query import QueryError
from reki.catalog import load_catalog
from reki.catalog.query_binding import CatalogSnapshot, plan_source_binding
from reki.query_collection import _validate_compatibility, read_grib_collection
from reki.readers.grib.reader import GribReader


@pytest.fixture(scope="module")
def assets(tmp_path_factory):
    script = Path(__file__).resolve().parents[2] / "fixtures/t09/generate.py"
    spec = importlib.util.spec_from_file_location("t11_assets", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = tmp_path_factory.mktemp("t11-grib")
    manifest = module.build(root)
    return root, manifest


def _plan(root, *, leads=None, levels=None, members=None, parameter="cedarkit.t", vertical=None):
    catalog = load_catalog(builtin=False, plugins=False, user=False, explicit={
        "api_version": "reki.catalog/v1", "datasets": [{"id": "grid", "source": {
            "name": "file-pattern", "args": [str(root), "baseline/f{forecast_hour_label}_m1.grib2"]}}]})
    query = {"api_version": "cedarkit.query/v1", "domain": "grid", "dataset": "grid",
             "parameter": parameter, "reference_time": "2026-08-30T00:00:00Z",
             "lead_time": leads or [f"PT{hour * 3600}S" for hour in range(0, 73, 6)],
             "vertical": vertical or {"type": "isobaric", "unit": "Pa", "values": levels or [50000, 85000]},
             "statistic": {"kind": "instant"}}
    if members is not None:
        query["member"] = members
    return plan_source_binding(query, snapshot=CatalogSnapshot(catalog, "t11-catalog"))


def _read(plan, paths, **kwargs):
    return read_grib_collection(plan, candidate_paths=paths,
                                native_parameters={"cedarkit.t": "t", "cedarkit.gh": "gh", "cedarkit.z": "z"},
                                member_roles={"0": "control", "1": "perturbation", "2": "perturbation"},
                                index_policy="off", **kwargs)


def _members():
    return [{"id": "0", "role": "control"}, {"id": "1", "role": "perturbation"},
            {"id": "2", "role": "perturbation"}]


def test_all_78_fields_are_organized_by_identity_not_file_order(assets):
    root, manifest = assets
    paths = [root / path for path in manifest["baseline_files"]]
    plan = _plan(root, members=_members())
    result = _read(plan, list(reversed(paths)))
    assert result.complete
    assert len(result.expected) == len(result.fields) == 78
    assert result.data.dims == ("lead_time", "isobaricInPa", "member", "latitude", "longitude")
    assert result.data.shape == (13, 2, 3, 3, 4)
    assert result.data.coords["member"].values.tolist() == ["0", "1", "2"]
    assert result.data.coords["member_role"].values.tolist() == ["control", "perturbation", "perturbation"]
    assert result.data.coords["isobaricInPa"].values.tolist() == [50000, 85000]
    assert result.data.attrs["units"] == "K"
    assert len(result.data.attrs["source_references"]) == 78
    for field in result.fields:
        np.testing.assert_array_equal(field.data.values,
                                      GribReader(None, field.reference.resource["locator"], index_policy="off")
                                      .all()[field.reference.field_locator["field_index"]].to_xarray().values)
    forward = _read(plan, paths)
    np.testing.assert_array_equal(result.data.values, forward.data.values)
    assert result.data.coords.equals(forward.data.coords)


def test_single_parameter_multiple_leads_without_member(assets):
    root, _ = assets
    plan = _plan(root, leads=["PT0S", "PT21600S"], levels=[50000], members=None)
    paths = [root / f"baseline/f{lead:03d}_m1.grib2" for lead in (0, 6)]
    result = _read(plan, paths)
    assert result.data.shape == (2, 1, 3, 4)
    assert result.data.dims == ("lead_time", "isobaricInPa", "latitude", "longitude")


def test_missing_defaults_to_error_and_partial_reports_exact_identity(assets):
    root, manifest = assets
    paths = [root / path for path in manifest["baseline_files"]
             if path != "baseline/f048_m2.grib2"] + [root / "cases/missing_replacement.grib2"]
    plan = _plan(root, members=_members())
    with pytest.raises(QueryError) as caught:
        _read(plan, paths)
    assert caught.value.code == "not_found"
    assert len(caught.value.context["missing"]) == 1
    result = _read(plan, paths, missing="partial")
    assert not result.complete and result.data is None
    assert len(result.fields) == 77
    assert result.missing[0]["lead_time"] == "PT172800S"
    assert result.missing[0]["vertical"]["values"] == 85000
    assert result.missing[0]["member"]["id"] == "2"


def test_absent_candidate_file_reports_path_and_expected_fields(assets):
    root, _ = assets
    absent = root / "baseline/f006_m1_absent.grib2"
    plan = _plan(root, leads=["PT21600S"], members=[_members()[1]])
    with pytest.raises(QueryError) as caught:
        _read(plan, [absent])
    assert caught.value.code == "not_found"
    assert len(caught.value.context["missing"]) == 2
    result = _read(plan, [absent], missing="partial")
    assert result.data is None and not result.complete
    assert len(result.missing) == 2
    assert result.missing_paths == (str(absent),)


def test_duplicate_and_grid_conflict_are_rejected(assets):
    root, manifest = assets
    paths = [root / path for path in manifest["baseline_files"]]
    plan = _plan(root, members=_members())
    with pytest.raises(QueryError) as caught:
        _read(plan, paths + [root / "cases/duplicate.grib2"])
    assert caught.value.code == "multiple_matches"
    assert caught.value.context["field_identity"]["member"]["id"] == "1"
    replaced = [path for path in paths if path.name != "f030_m2.grib2"]
    replaced.append(root / "cases/grid_conflict.grib2")
    with pytest.raises(QueryError) as caught:
        _read(plan, replaced, missing="partial")
    assert caught.value.code == "incompatible_grid"


def test_native_unit_pair_is_not_combined_as_one_parameter(assets):
    root, _ = assets
    path = root / "cases/unit_pair.grib2"
    gh = _read(_plan(root, leads=["PT129600S"], levels=[50000], members=[_members()[0]],
                     parameter="cedarkit.gh"), [path])
    z = _read(_plan(root, leads=["PT129600S"], levels=[50000], members=[_members()[0]],
                    parameter="cedarkit.z"), [path])
    assert gh.data.attrs["units"] == "gpm"
    assert z.data.attrs["units"] == "m**2 s**-2"
    assert gh.data.attrs["units"] != z.data.attrs["units"]
    # Exercise the merge guard with two actual GRIB fields under one stable identity.
    with pytest.raises(QueryError) as incompatible:
        _validate_compatibility((gh.fields[0], replace(z.fields[0], identity=gh.fields[0].identity)))
    assert incompatible.value.code == "incompatible_units"
    with pytest.raises(QueryError) as caught:
        _read(_plan(root, leads=["PT129600S"], levels=[50000], members=[_members()[0]],
                    parameter=["cedarkit.gh", "cedarkit.z"]), [path])
    assert caught.value.code == "unsupported"
    assert caught.value.path == "/query/parameter"


def test_incompatible_level_type_is_reported_missing(assets):
    root, _ = assets
    plan = _plan(root, leads=["PT0S"], members=[_members()[1]],
                 vertical={"type": "surface"})
    with pytest.raises(QueryError) as caught:
        _read(plan, [root / "baseline/f000_m1.grib2"])
    assert caught.value.code == "not_found"
    assert caught.value.context["missing"][0]["vertical"]["type"] == "surface"


def test_outside_candidate_and_unmapped_member_are_rejected(assets, tmp_path):
    root, _ = assets
    plan = _plan(root, leads=["PT0S"], levels=[50000], members=[_members()[1]])
    with pytest.raises(QueryError) as caught:
        _read(plan, [root / "baseline/f000_m1.grib2", tmp_path / "outside.grib2"])
    assert caught.value.code == "unsupported"
    assert caught.value.path == "/resource/locator"
    with pytest.raises(QueryError) as caught:
        read_grib_collection(plan, candidate_paths=[root / "baseline/f000_m1.grib2"],
                             native_parameters={"cedarkit.t": "t"})
    assert caught.value.path == "/query/member"
