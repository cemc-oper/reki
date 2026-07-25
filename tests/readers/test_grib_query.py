"""Tests for the GRIB lazy query object (GribReader)."""

import numpy as np
import pytest
import xarray as xr

import reki.readers.grib.eccodes.field
import reki.readers.grib.eccodes.message
from reki.core import Source
from reki.readers.grib.reader import GribField, GribReader



class FakeSource(Source):
    pass


@pytest.fixture
def grib_reader(grib2_gfs_basic_file_path):
    return GribReader(FakeSource(), grib2_gfs_basic_file_path)


class TestSel:
    def test_sel_returns_new_reader(self, grib_reader):
        sub = grib_reader.sel(parameter="t")
        assert sub is not grib_reader
        assert isinstance(sub, GribReader)

    def test_sel_accumulates_filters(self, grib_reader):
        sub = grib_reader.sel(parameter="t").sel(level_type="pl", level=850)
        assert sub.filters == {
            "parameter": "t", "level_type": "pl", "level": 850,
        }
        # original reader is unchanged
        assert grib_reader.filters == {}

    def test_sel_keeps_extra_grib_keys(self, grib_reader):
        sub = grib_reader.sel(parameter="t", stepRange=105)
        assert sub.filters["stepRange"] == 105

    def test_engine_must_be_valid(self, grib2_gfs_basic_file_path):
        with pytest.raises(ValueError, match="engine"):
            GribReader(FakeSource(), grib2_gfs_basic_file_path, engine="bogus")


class TestFirst:
    def test_first_matches_legacy_load_field_from_file(
            self, grib_reader, grib2_gfs_basic_file_path
    ):
        field = grib_reader.sel(
            parameter="t", level_type="pl", level=850
        ).first()
        assert isinstance(field, GribField)
        expected = reki.readers.grib.eccodes.field.load_field_from_file(
            grib2_gfs_basic_file_path, "t", level_type="pl", level=850
        )
        xr.testing.assert_identical(field.to_xarray(), expected)

    def test_first_multi_levels_concat(
            self, grib_reader, grib2_gfs_basic_file_path
    ):
        field = grib_reader.sel(
            parameter="t", level_type="pl", level=[850, 500]
        ).first()
        data = field.to_xarray()
        assert isinstance(data, xr.DataArray)
        assert data.sizes["pl"] == 2
        expected = reki.readers.grib.eccodes.field.load_field_from_file(
            grib2_gfs_basic_file_path, "t", level_type="pl", level=[850, 500]
        )
        xr.testing.assert_identical(data, expected)

    def test_first_not_found_returns_none(self, grib_reader):
        assert grib_reader.sel(
            parameter="t", level_type="pl", level=12345
        ).first() is None

    def test_first_by_count(self, grib_reader, grib2_gfs_basic_file_path):
        field = grib_reader.sel(count=25).first()
        data = field.to_xarray()
        assert isinstance(data, xr.DataArray)
        # message 25 is 2m temperature; the count path decodes without a
        # field name hint, so the name comes from the CEMC param table.
        expected = reki.readers.grib.eccodes.field.load_field_from_file(
            grib2_gfs_basic_file_path, "2t",
            level_type="heightAboveGround", level=2,
        )
        np.testing.assert_array_equal(data.values, expected.values)

    def test_first_by_count_out_of_range(self, grib_reader):
        assert grib_reader.sel(count=99999).first() is None

    def test_first_with_cfgrib_engine(
            self, grib_reader, grib2_gfs_basic_file_path
    ):
        reader = GribReader(
            FakeSource(), grib2_gfs_basic_file_path, engine="cfgrib"
        )
        field = reader.sel(parameter="2t", level=2).first()
        assert isinstance(field, GribField)
        # cfgrib names variables by their CF name
        assert field.to_xarray().name == "t2m"


class TestToXarray:
    def test_single_match_returns_data_array(self, grib_reader):
        data = grib_reader.sel(
            parameter="2t", level_type="heightAboveGround", level=2
        ).to_xarray()
        assert isinstance(data, xr.DataArray)
        assert data.name == "2t"

    def test_multi_levels_merge_into_dataset(self, grib_reader):
        data = grib_reader.sel(
            parameter="t", level_type="pl", level=[850, 500]
        ).to_xarray()
        assert isinstance(data, xr.Dataset)
        assert "t" in data.data_vars
        assert data.sizes["pl"] == 2

    def test_multi_hypercubes_return_dataset_list(self, grib_reader):
        data = grib_reader.sel(
            parameter="u",
            level_type=["heightAboveGround", "isobaricInPa"],
        ).to_xarray()
        assert isinstance(data, list)
        assert len(data) == 2
        assert all(isinstance(ds, xr.Dataset) for ds in data)

    def test_no_match_returns_none(self, grib_reader):
        assert grib_reader.sel(
            parameter="t", level_type="pl", level=12345
        ).to_xarray() is None

    def test_cfgrib_single_match(self, grib2_gfs_basic_file_path):
        reader = GribReader(
            FakeSource(), grib2_gfs_basic_file_path, engine="cfgrib"
        )
        data = reader.sel(
            parameter="2t", level_type="heightAboveGround", level=2
        ).to_xarray()
        assert isinstance(data, xr.DataArray)
        # cfgrib names variables by their CF name
        assert data.name == "t2m"

    def test_cfgrib_multi_levels(self, grib2_gfs_basic_file_path):
        reader = GribReader(
            FakeSource(), grib2_gfs_basic_file_path, engine="cfgrib"
        )
        data = reader.sel(
            parameter="t", level_type="pl", level=[850, 500]
        ).to_xarray()
        assert isinstance(data, xr.Dataset)
        assert "t" in data.data_vars


class TestUnsupportedCollectionAPI:
    def test_len_not_supported(self, grib_reader):
        with pytest.raises(NotImplementedError, match="metadata index"):
            len(grib_reader)

    def test_getitem_not_supported(self, grib_reader):
        with pytest.raises(NotImplementedError, match="metadata index"):
            grib_reader[0]
