"""Tests for the NetCDF / GrADS / table readers."""

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from reki.core import Source
from reki.readers import UnknownReader, reader
from reki.readers.grads import GradsReader
from reki.readers.netcdf import NetCDFReader
from reki.readers.table import TableReader


class FakeSource(Source):
    pass


@pytest.fixture
def grads_files(tmp_path):
    ctl_path = tmp_path / "test.ctl"
    bin_path = tmp_path / "test.bin"
    ctl_path.write_text(
        "dset ^test.bin\n"
        "title test\n"
        "undef -999.0\n"
        "xdef 3 linear 100.0 1.0\n"
        "ydef 2 linear 20.0 1.0\n"
        "zdef 2 linear 1000 50\n"
        "tdef 1 linear 00Z01Jan2020 1hr\n"
        "vars 1\n"
        "t 2 99 temperature\n"
        "endvars\n"
    )
    # two records (z=1000, z=950) of a 2x3 float32 grid
    values = np.arange(12, dtype="<f4")
    bin_path.write_bytes(values.tobytes())
    # the kernel flips latitude by default (latitude_direction="degree_north")
    return ctl_path, values.reshape(2, 2, 3)[:, ::-1, :]


@pytest.fixture
def csv_file(tmp_path):
    path = tmp_path / "obs.csv"
    path.write_text("station,tem\n0001,280.5\n0002,281.0\n")
    return path


class TestNetCDFReader:
    def test_legacy_netcdf_entry_point_is_reader_entry_point(self):
        from reki.format.netcdf import load_field_from_file as legacy
        from reki.readers.netcdf import load_field_from_file as current

        assert legacy is current
    @pytest.mark.parametrize(
        "magic", [b"\x89HDF\r\n\x1a\n" + b"\x00" * 56, b"CDF\x01" + b"\x00" * 60]
    )
    def test_dispatch_claims_netcdf_magic(self, tmp_path, magic):
        path = tmp_path / "data.nc"
        path.write_bytes(magic)
        r = reader(FakeSource(), path)
        assert isinstance(r, NetCDFReader)

    def test_magic_rejection(self, tmp_path):
        from reki.readers.netcdf.reader import READER

        path = tmp_path / "data.grib"
        path.write_bytes(b"GRIB" + b"\x00" * 32)
        assert READER(FakeSource(), path, magic=b"GRIB" + b"\x00" * 32) is None

    def test_to_xarray_delegates_to_xarray_open_dataset(
            self, tmp_path, monkeypatch
    ):
        import reki.readers.netcdf.reader as netcdf_reader_module

        seen = {}

        def fake_open_dataset(path, **kwargs):
            seen["path"] = path
            seen["kwargs"] = kwargs
            return "dataset"

        monkeypatch.setattr(
            netcdf_reader_module.xr, "open_dataset", fake_open_dataset
        )
        r = NetCDFReader(FakeSource(), tmp_path / "data.nc")
        assert r.to_xarray(engine="h5netcdf") == "dataset"
        assert seen["kwargs"] == {"engine": "h5netcdf"}


class TestGradsReader:
    def test_legacy_grads_entry_point_is_reader_entry_point(self):
        from reki.format.grads import load_field_from_file as legacy
        from reki.readers.grads import load_field_from_file as current

        assert legacy is current
    def test_dispatch_claims_ctl(self, grads_files):
        ctl_path, _ = grads_files
        r = reader(FakeSource(), ctl_path)
        assert isinstance(r, GradsReader)

    def test_sel_accumulates_filters(self, grads_files):
        ctl_path, _ = grads_files
        r = GradsReader(FakeSource(), ctl_path)
        sub = r.sel(parameter="t", level_type="pl", level=1000)
        assert sub is not r
        assert sub.filters == {
            "parameter": "t", "level_type": "pl", "level": 1000,
        }
        assert r.filters == {}

    def test_to_xarray_requires_parameter(self, grads_files):
        ctl_path, _ = grads_files
        r = GradsReader(FakeSource(), ctl_path)
        with pytest.raises(ValueError, match="parameter"):
            r.to_xarray()

    def test_to_xarray_single_level(self, grads_files):
        ctl_path, values = grads_files
        data = reader(FakeSource(), ctl_path).sel(
            parameter="t", level_type="pl", level=1000
        ).to_xarray()
        assert isinstance(data, xr.DataArray)
        assert data.name == "t"
        np.testing.assert_array_equal(data.values, values[0])

    def test_to_xarray_all_levels(self, grads_files):
        ctl_path, values = grads_files
        data = reader(FakeSource(), ctl_path).sel(
            parameter="t", level_type="pl"
        ).to_xarray()
        assert data.sizes["pl"] == 2
        np.testing.assert_array_equal(data.values, values)


class TestTableReader:
    def test_legacy_table_entry_point_matches_reader(self, csv_file):
        from reki.format.table import load_table_from_file as legacy
        from reki.readers.table import load_table_from_file as current

        pd.testing.assert_frame_equal(legacy(csv_file), current(csv_file))

    def test_dispatch_claims_text_table_in_deeper_pass(self, csv_file):
        r = reader(FakeSource(), csv_file)
        assert isinstance(r, TableReader)

    def test_quick_pass_does_not_claim(self, csv_file):
        from reki.readers.table.reader import READER

        magic = csv_file.read_bytes()[:64]
        assert READER(
            FakeSource(), csv_file, magic=magic, deeper_check=False
        ) is None

    def test_to_pandas(self, csv_file):
        df = reader(FakeSource(), csv_file).to_pandas()
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["station", "tem"]
        assert len(df) == 2

    def test_unknown_extension_falls_back(self, tmp_path):
        path = tmp_path / "data.xyz"
        path.write_bytes(b"1 2 3\n4 5 6\n")
        r = reader(FakeSource(), path)
        assert isinstance(r, UnknownReader)
