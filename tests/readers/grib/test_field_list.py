import eccodes

from reki import FieldList
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
