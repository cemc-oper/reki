import eccodes
import pandas as pd
import pytest

from reki import DataNotFoundError, FieldList, FieldQuery
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


def test_hot_index_first_and_one_avoid_header_scans(tmp_path):
    path = tmp_path / "fields.grib"
    root = tmp_path / "index"
    _write(path)
    # Build once, then use a new reader to model independent queries.
    GribReader(None, path, index_policy="auto", index_dir=root).all()
    with collect_io_metrics() as metrics:
        reader = GribReader(None, path, index_policy="auto", index_dir=root)
        assert reader.sel(level=850).first().metadata.level == 850
        # ``t`` resolves to the native discipline/category/number triplet;
        # that projection must be present in indexed metadata as well.
        assert reader.sel(parameter="t", level_type="pl", level=500).one().metadata.level == 500
        snapshot = metrics.snapshot()
    assert snapshot["index_hit_count"] == 2
    assert snapshot["grib_header_scan_count"] == 0
    assert snapshot["value_decode_count"] == 0


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


def test_forecast_metadata_matches_between_scan_and_hot_index(tmp_path):
    path = tmp_path / "timed.grib"
    root = tmp_path / "index"
    _write_timed_field(path)

    with collect_io_metrics() as metrics:
        scanned = GribReader(None, path, index_policy="off").all().one().metadata
        assert metrics.snapshot()["value_decode_count"] == 0

    # Build then reopen so the second access must project metadata from SQLite.
    GribReader(None, path, index_policy="auto", index_dir=root).all()
    with collect_io_metrics() as metrics:
        indexed = GribReader(None, path, index_policy="auto", index_dir=root).all().one().metadata
        assert metrics.snapshot()["grib_header_scan_count"] == 0
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
    assert isinstance(collected[0].error, DataNotFoundError)
    assert collected[0].position == 0


def test_fetch_many_with_unindexed_extra_uses_one_header_pass(tmp_path):
    path = tmp_path / "fields.grib"
    _write(path)
    with collect_io_metrics() as metrics:
        results = GribReader(None, path, index_policy="auto", index_dir=tmp_path / "index").fetch_many(
            [{"discipline": 0, "level": 850}, {"discipline": 0, "level": 500}],
            cardinality="one",
        )
        assert [item.metadata.level for item in results] == [850, 500]
        assert metrics.snapshot()["grib_header_scan_count"] == 2
