import eccodes
import pandas as pd
import pytest

from cedarkit_query import QueryError
from reki.core.field_list import _ReaderFields as FieldList
from reki.core.field_query import _ReaderQuery as FieldQuery
from reki.diagnostics import collect_io_metrics
from reki.readers.grib.reader import GribReader


def _write(path):
    with path.open("wb") as output:
        for short_name, level in (("t", 850), ("t", 500)):
            message = eccodes.codes_grib_new_from_samples("GRIB2")
            try:
                eccodes.codes_set(message, "shortName", short_name)
                eccodes.codes_set(message, "typeOfLevel", "isobaricInhPa")
                eccodes.codes_set(message, "level", level)
                eccodes.codes_write(message, output)
            finally:
                eccodes.codes_release(message)


def _write_timed_field(path):
    """A 6--9 hour statistical product with an unambiguous valid time."""
    with path.open("wb") as output:
        message = eccodes.codes_grib_new_from_samples("GRIB2")
        try:
            eccodes.codes_set(message, "shortName", "t")
            eccodes.codes_set(message, "typeOfLevel", "isobaricInhPa")
            eccodes.codes_set(message, "level", 850)
            eccodes.codes_set(message, "dataDate", 20240102)
            eccodes.codes_set(message, "dataTime", 300)
            eccodes.codes_set(message, "productDefinitionTemplateNumber", 8)
            eccodes.codes_set(message, "indicatorOfUnitForTimeRange", 1)
            eccodes.codes_set(message, "lengthOfTimeRange", 3)
            eccodes.codes_set(message, "forecastTime", 6)
            eccodes.codes_write(message, output)
        finally:
            eccodes.codes_release(message)


def _write_soil_layer(path):
    """Write the registry's ``st(0-10)`` fixed-surface combination."""
    with path.open("wb") as output:
        message = eccodes.codes_grib_new_from_samples("GRIB2")
        try:
            eccodes.codes_set(message, "discipline", 0)
            eccodes.codes_set(message, "parameterCategory", 0)
            eccodes.codes_set(message, "parameterNumber", 0)
            eccodes.codes_set(message, "typeOfFirstFixedSurface", 106)
            eccodes.codes_set(message, "scaleFactorOfFirstFixedSurface", 1)
            eccodes.codes_set(message, "scaledValueOfFirstFixedSurface", 0)
            eccodes.codes_set(message, "typeOfSecondFixedSurface", 106)
            eccodes.codes_set(message, "scaleFactorOfSecondFixedSurface", 1)
            eccodes.codes_set(message, "scaledValueOfSecondFixedSurface", 1)
            eccodes.codes_write(message, output)
        finally:
            eccodes.codes_release(message)


def test_all_is_lazy_and_uses_index_then_field_offset(tmp_path):
    path = tmp_path / "fields.grib"
    _write(path)
    with collect_io_metrics() as metrics:
        fields = GribReader(None, path, index_dir=tmp_path / "index").all()
        assert isinstance(fields, FieldList)
        assert len(fields) == 2
        assert fields[0].metadata.index == 0
        assert fields.sel(level_type="pl", level=850).one().metadata.level == 850
        assert metrics.snapshot()["value_decode_count"] == 0
        assert fields[0].to_xarray().name == "t"
    assert metrics.snapshot()["value_decode_count"] == 1


def test_all_off_keeps_metadata_scan_without_index(tmp_path):
    path = tmp_path / "fields.grib"
    _write(path)
    fields = GribReader(None, path, index_policy="off").all()
    assert len(fields) == 2


@pytest.mark.parametrize("policy", ["auto", "readonly", "refresh"])
def test_retired_index_policy_is_explicitly_rejected(tmp_path,policy):
    with pytest.raises(QueryError, match="retired"):
        GribReader(None,tmp_path/"missing.grib2",index_policy=policy)


def test_exploration_is_metadata_only_and_json_safe(tmp_path):
    path = tmp_path / "fields.grib"
    _write(path)
    reader = GribReader(None, path, index_policy="off")
    with collect_io_metrics() as metrics:
        assert reader.capabilities.metadata
        assert reader.summary()["field_count"] == 2
        assert reader.unique("parameter") == ["t"]
        assert len(reader.head(1)) == 1
        assert list(reader.ls().columns) == [
            "index", "parameter", "level_type", "level", "start_time",
            "step", "valid_time", "step_type", "member", "grid_type",
        ]
        assert reader.all().json(["index", "level"]) == [
            {"index": 0, "level": 850.0}, {"index": 1, "level": 500.0},
        ]
        assert metrics.snapshot()["value_decode_count"] == 0
    with pytest.raises(TypeError):
        reader.where("level == 850")


def test_forecast_metadata_matches_between_independent_scans(tmp_path):
    path = tmp_path / "timed.grib"
    root = tmp_path / "index"
    _write_timed_field(path)

    with collect_io_metrics() as metrics:
        scanned = GribReader(None, path, index_policy="off").all().one().metadata
        assert metrics.snapshot()["value_decode_count"] == 0

    # A fresh scan must preserve the same header metadata without an index.
    GribReader(None, path, index_policy="off", index_dir=root).all()
    with collect_io_metrics() as metrics:
        indexed = GribReader(None, path, index_policy="off", index_dir=root).all().one().metadata
        assert metrics.snapshot()["grib_header_scan_count"] == 1
        assert metrics.snapshot()["value_decode_count"] == 0

    expected = {
        "start_time": pd.Timestamp("2024-01-02 03:00:00"),
        "step": pd.Timedelta(hours=9),
        # The sample's explicit validity keys are authoritative; this also
        # verifies that metadata follows the same ecCodes value as decoding.
        "valid_time": pd.Timestamp("2024-01-02 03:00:00"),
        "time_range": pd.Timedelta(hours=3),
    }
    assert {key: getattr(scanned, key) for key in expected} == expected
    assert {key: getattr(indexed, key) for key in expected} == expected
    assert GribReader(None, path, index_policy="off").ls(["step"]).iloc[0, 0] == pd.Timedelta(hours=9)


def test_refining_a_step_query_preserves_public_fieldlist_merge(tmp_path):
    path = tmp_path / "timed.grib"
    _write_timed_field(path)

    fields = GribReader(None, path, index_policy="off").sel(step=9).all()
    selected = fields.sel(level=850)

    assert len(selected) == 1
    assert selected.one().metadata.step == pd.Timedelta(hours=9)
    assert selected.to_xarray().name == "t"


def test_independent_scans_preserve_native_fixed_surfaces(tmp_path):
    path = tmp_path / "soil.grib"
    root = tmp_path / "index"
    _write_soil_layer(path)

    scanned = GribReader(None, path, index_policy="off").all().one()
    assert "cemc_name" not in scanned.metadata.extra
    assert "wgrib2_name" not in scanned.metadata.extra
    assert scanned.to_xarray().name == scanned.metadata.parameter

    GribReader(None, path, index_policy="off", index_dir=root).all()
    indexed = GribReader(None, path, index_policy="off", index_dir=root).all().one()
    assert indexed.metadata.extra == scanned.metadata.extra


def test_fetch_many_uses_one_metadata_scan_and_preserves_duplicates(tmp_path):
    path = tmp_path / "fields.grib"
    _write(path)
    reader = GribReader(None, path, index_policy="off")
    query = FieldQuery(parameter="t", level_type="pl", level=850)
    with collect_io_metrics() as metrics:
        results = reader.fetch_many([query, {"level": 500}, query], cardinality="one")
        assert [item.metadata.level for item in results] == [850, 500, 850]
        assert metrics.snapshot()["grib_header_scan_count"] == 2
        assert metrics.snapshot()["value_decode_count"] == 0
    collected = reader.fetch_many([{"level": 100}, {"level": 850}], cardinality="one", errors="collect")
    assert isinstance(collected[0].error, QueryError) and collected[0].error.code == "no_match"
    assert collected[0].position == 0


def test_fetch_many_with_unindexed_extra_uses_one_header_pass(tmp_path):
    path = tmp_path / "fields.grib"
    _write(path)
    with collect_io_metrics() as metrics:
        results = GribReader(None, path, index_policy="off", index_dir=tmp_path / "index").fetch_many(
            [{"discipline": 0, "level": 850}, {"discipline": 0, "level": 500}],
            cardinality="one",
        )
        assert [item.metadata.level for item in results] == [850, 500]
        assert metrics.snapshot()["grib_header_scan_count"] == 2
