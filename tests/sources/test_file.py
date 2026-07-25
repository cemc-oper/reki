"""Tests for FileSource and the from_source -> reader dispatch chain."""

import numpy as np
import pytest
import xarray as xr

import reki
from reki.readers import UnknownReader
from reki.readers.grib import GribReader
from reki.sources import get_source
from reki.sources.file import FileSource


@pytest.fixture
def netcdf_magic_file(tmp_path):
    path = tmp_path / "data.nc"
    path.write_bytes(b"\x89HDF\r\n\x1a\n" + b"\x00" * 56)
    return path


class TestFileSource:
    def test_mutate_returns_self(self, tmp_path):
        src = FileSource(tmp_path / "data.bin")
        assert src.mutate() is src

    def test_name_is_set_by_source_maker(self, tmp_path):
        assert get_source("file", tmp_path / "data.bin").name == "file"

    def test_expand_user(self):
        assert not FileSource("~/data.bin").path.startswith("~")

    def test_fspath(self, tmp_path):
        import os

        src = FileSource(tmp_path / "data.bin")
        assert os.fspath(src) == str(tmp_path / "data.bin")


class TestFromSourceFile:
    def test_grib_file_dispatches_to_grib_reader(self, grib2_gfs_basic_file_path):
        ds = reki.from_source("file", grib2_gfs_basic_file_path)
        assert isinstance(ds, GribReader)

    def test_grib_query_chain_matches_legacy(
            self, grib2_gfs_basic_file_path
    ):
        from reki.format.grib.eccodes import load_field_from_file

        data = reki.from_source("file", grib2_gfs_basic_file_path).sel(
            parameter="t", level_type="pl", level=850
        ).first().to_xarray()
        expected = load_field_from_file(
            grib2_gfs_basic_file_path, "t", level_type="pl", level=850
        )
        xr.testing.assert_identical(data, expected)

    def test_netcdf_magic_dispatches_to_netcdf_reader(self, netcdf_magic_file):
        from reki.readers.netcdf import NetCDFReader

        ds = reki.from_source("file", netcdf_magic_file)
        assert isinstance(ds, NetCDFReader)

    def test_explicit_reader_skips_detection(self, grib2_gfs_basic_file_path):
        ds = reki.from_source(
            "file", grib2_gfs_basic_file_path, reader="grib"
        )
        assert isinstance(ds, GribReader)

    def test_unknown_format_returns_unknown_reader(self, tmp_path):
        path = tmp_path / "data.xyz"
        path.write_bytes(b"\x00\x01\x02\x03")
        ds = reki.from_source("file", path)
        assert isinstance(ds, UnknownReader)
        assert ds.to_bytes() == b"\x00\x01\x02\x03"

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            reki.from_source("file", tmp_path / "missing.grib")

    def test_memory_source_still_returns_source(self):
        data_array = xr.DataArray(np.arange(3), name="t")
        src = reki.from_source("memory", data_array)
        assert src.to_xarray() is data_array
