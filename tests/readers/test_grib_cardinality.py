"""Strict 0/1/N cardinality contract, using deterministic local GRIB samples."""
import eccodes
import pytest

from reki import DataNotFoundError, MultipleFieldsMatchedError
from reki.readers.grib.reader import GribReader


def _write_messages(path, levels):
    with open(path, "wb") as handle:
        for level in levels:
            message = eccodes.codes_grib_new_from_samples("GRIB2")
            try:
                eccodes.codes_set(message, "shortName", "t")
                eccodes.codes_set(message, "typeOfLevel", "isobaricInhPa")
                eccodes.codes_set(message, "level", level)
                eccodes.codes_write(message, handle)
            finally:
                eccodes.codes_release(message)


@pytest.mark.parametrize("engine", ["eccodes", "cfgrib"])
def test_strict_cardinality_matrix(engine, tmp_path):
    path = tmp_path / "fields.grib"
    _write_messages(path, [850, 500])
    base = GribReader(None, path, engine=engine).sel(parameter="t", level_type="pl")

    assert base.sel(level=700).first() is None
    assert base.sel(level=700).one_or_none() is None
    with pytest.raises(DataNotFoundError) as missing:
        base.sel(level=700).one()
    assert missing.value.match_count == 0

    assert base.sel(level=850).one().to_xarray().name == "t"
    assert base.sel(level=850).one_or_none().to_xarray().name == "t"

    assert base.first().to_xarray().name == "t"
    with pytest.raises(MultipleFieldsMatchedError) as multiple:
        base.one()
    assert multiple.value.match_count == 2


def test_eccodes_multiple_match_stops_at_second_header_without_values_decode(tmp_path, monkeypatch):
    path = tmp_path / "fields.grib"
    _write_messages(path, [850, 700, 500])
    calls = {"headers": 0, "values": 0}
    original_header = eccodes.codes_grib_new_from_file
    original_values = eccodes.codes_get_double_array

    def header(*args, **kwargs):
        calls["headers"] += 1
        return original_header(*args, **kwargs)

    def values(*args, **kwargs):
        calls["values"] += 1
        return original_values(*args, **kwargs)

    monkeypatch.setattr(eccodes, "codes_grib_new_from_file", header)
    monkeypatch.setattr(eccodes, "codes_get_double_array", values)
    reader = GribReader(None, path).sel(parameter="t", level_type="pl")
    with pytest.raises(MultipleFieldsMatchedError):
        reader.one()
    assert calls == {"headers": 2, "values": 0}
