"""T16: legacy format entry points and the public GRIB boundary."""

import json

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from click.testing import CliRunner

from cedarkit_query import QueryError
from reki import FieldQuery, SourceSpec, from_source
from reki.catalog import load_catalog
from reki.catalog.query_binding import CatalogSnapshot, plan_source_binding
from reki.cli import cli
from reki.query_adapter import query_from_field_query
from reki.query_collection import read_grib_collection
from reki.query_locator import list_fields, locate_fields
from reki.readers.grads import GradsReader
from reki.readers.netcdf import NetCDFReader
from reki.readers.table import TableReader, load_nwpc_obs_from_file
from reki.sources.file_pattern import FilePatternSource
from reki.sources.local import LocalSource


def _plan(root, name):
    catalog = load_catalog(builtin=False, plugins=False, user=False, explicit={
        "api_version": "reki.catalog/v1", "datasets": [{"id": "grid", "source": {
            "name": "file-pattern", "args": [str(root), name]}}]})
    query = {"api_version": "cedarkit.query/v1", "domain": "grid", "dataset": "grid",
             "parameter": "cedarkit.t", "reference_time": "2026-08-30T00:00:00Z",
             "lead_time": "PT0S", "vertical": {"type": "surface"},
             "statistic": {"kind": "instant"}}
    return plan_source_binding(query, snapshot=CatalogSnapshot(catalog, "t16-catalog"))


def _grads(path):
    (path.parent / "field.bin").write_bytes(np.arange(4, dtype="<f4").tobytes())
    path.write_text("dset ^field.bin\ntitle test\nundef -999\nxdef 2 linear 100 1\n"
                    "ydef 2 linear 20 1\nzdef 1 levels 850\ntdef 1 linear 00Z01Jan2020 1hr\n"
                    "vars 1\nt 1 99 temperature\nendvars\n")


@pytest.mark.parametrize("kind", ["netcdf", "table", "grads"])
def test_legacy_readers_still_load_while_public_grib_queries_reject_them(tmp_path, kind):
    if kind == "netcdf":
        path = tmp_path / "field.nc"
        xr.Dataset({"temperature": ("x", [280.0, 281.0])}).to_netcdf(path, engine="scipy")
        old = from_source(SourceSpec("file", args=(str(path),)))
        assert isinstance(old, NetCDFReader)
        assert old.to_xarray()["temperature"].values.tolist() == [280.0, 281.0]
    elif kind == "table":
        path = tmp_path / "field.csv"
        path.write_text("station,tem\n001,280.5\n")
        old = from_source(SourceSpec("file", args=(str(path),)))
        assert isinstance(old, TableReader)
        assert old.to_pandas()["tem"].tolist() == [280.5]
    else:
        path = tmp_path / "field.ctl"
        _grads(path)
        old = from_source(SourceSpec("file", args=(str(path),)))
        assert isinstance(old, GradsReader)
        assert old.sel(parameter="t", level_type="pl", level=850).to_xarray().shape == (2, 2)

    plan = _plan(tmp_path, path.name)
    for action in (
        lambda: locate_fields(plan, native_parameters={"cedarkit.t": "t"}, index_policy="off"),
        lambda: list_fields(plan, index_policy="off"),
        lambda: read_grib_collection(plan, candidate_paths=[path],
                                     native_parameters={"cedarkit.t": "t"}, index_policy="off"),
    ):
        with pytest.raises(QueryError) as caught:
            action()
        assert caught.value.code == "unsupported"
        assert caught.value.path == "/binding/reader"


def test_nwpc_table_compatibility_entry_point(tmp_path):
    path = tmp_path / "RGWST.txt"
    path.write_text("RGWST 2026 08 30 00 0 0 0 0\n"
                    + " ".join(str(value) for value in range(13)) + "\n"
                    + " ".join(str(value) for value in range(13, 25)) + "\n"
                    + "END\n")
    from reki.format.table import load_nwpc_obs_from_file as legacy

    assert legacy is load_nwpc_obs_from_file
    result = legacy(path)
    assert len(result) == 1
    assert result["obs_time"].iloc[0] == pd.Timestamp("2026-08-30T00:00:00")
    assert result["TEM"].iloc[0] == 8


def test_public_cli_rejects_non_grib_without_silent_no_match(tmp_path):
    path = tmp_path / "field.nc"
    xr.Dataset({"temperature": ("x", [280.0])}).to_netcdf(path, engine="scipy")
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({"api_version": "reki.catalog/v1", "datasets": [
        {"id": "grid", "source": {"name": "file-pattern", "args": [str(tmp_path), path.name]}}]}))
    request = {"api_version": "cedarkit.request/v1", "action": "locate",
               "query": _plan(tmp_path, path.name).query.to_dict()}
    result = CliRunner().invoke(cli, ["request", "--catalog", str(catalog),
                                      "--native-parameter", "cedarkit.t=t",
                                      "locate", "--input-format", "json"], input=json.dumps(request))
    assert result.exit_code == 4, result.output
    assert json.loads(result.output)["error"]["code"] == "unsupported"
    legacy = CliRunner().invoke(cli, ["ls", str(path), "--json"])
    assert legacy.exit_code == 4


def test_legacy_zero_lead_defaults_stay_outside_public_query(tmp_path):
    start = "2026083000"
    assert FilePatternSource(tmp_path, "f{forecast_hour_label}.grib2",
                             start_time=start).resolve_path().name == "f000.grib2"
    assert LocalSource("grid", start_time=start).forecast_time == "0"
    with pytest.raises(QueryError) as caught:
        query_from_field_query("grid", FieldQuery(), "cedarkit.t", "2026-08-30T00:00:00Z", None)
    assert caught.value.path == "/query/lead_time"
