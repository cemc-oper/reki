"""Tests for the CMADaaS reader (Grid*2D / Array2D → xarray/pandas).

Real nuwe-cmadaas data classes are used with fake data; no MUSIC
service is involved.
"""

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from nuwe_cmadaas.music.data import (
    Array2D,
    GridArray2D,
    GridScalar2D,
    GridVector2D,
)

import reki
from reki.readers.cmadaas import MEMORY_READER, CmadaasReader


def read(buf):
    """Wrap ``buf`` in a memory source and dispatch to the cmadaas reader."""
    return reki.sources.get_source("memory", buf, reader="cmadaas").to_data_object()


@pytest.fixture
def grid_array():
    """A 2x3 grid; explicit lats/lons with lats != lons catches the
    upstream ``lons = self.lats`` bug this reader works around."""
    return GridArray2D(
        data=np.arange(6, dtype=float).reshape(2, 3),
        start_lat=0, end_lat=10, lat_count=2,
        start_lon=100, end_lon=120, lon_count=3,
        lats=[5.0, 15.0], lons=[101.0, 102.0, 103.0],
        units="K", user_element_name="TEM",
    )


class TestGridArray2D:
    def test_explicit_coords(self, grid_array):
        field = read(grid_array).to_xarray()
        assert isinstance(field, xr.DataArray)
        assert field.name == "TEM"
        assert field.attrs["units"] == "K"
        assert field.latitude.values.tolist() == [5.0, 15.0]
        # must be lons, not lats (the upstream bug)
        assert field.longitude.values.tolist() == [101.0, 102.0, 103.0]
        assert field.values[0, 0] == 0.0
        assert field.values[1, 2] == 5.0

    def test_linspace_coords_when_lists_empty(self, grid_array):
        grid_array.lats = []
        grid_array.lons = []
        field = read(grid_array).to_xarray()
        assert field.latitude.values.tolist() == [0.0, 10.0]
        assert field.longitude.values.tolist() == [100.0, 110.0, 120.0]

    def test_flat_data_is_reshaped(self, grid_array):
        grid_array.data = np.arange(6, dtype=float)
        field = read(grid_array).to_xarray()
        assert field.shape == (2, 3)

    def test_coord_attrs(self, grid_array):
        field = read(grid_array).to_xarray()
        assert field.latitude.attrs["units"] == "degrees_north"
        assert field.longitude.attrs["units"] == "degrees_east"

    def test_to_pandas_not_supported(self, grid_array):
        with pytest.raises(NotImplementedError, match="to_pandas"):
            read(grid_array).to_pandas()


class TestGridScalar2D:
    def test_to_xarray(self):
        grid = GridScalar2D(
            data=np.ones((2, 2)),
            start_lat=0, end_lat=1, lat_count=2,
            start_lon=0, end_lon=1, lon_count=2,
            lats=[], lons=[], units="mm", user_element_name="RAIN",
        )
        field = read(grid).to_xarray()
        assert isinstance(field, xr.DataArray)
        assert field.name == "RAIN"
        assert field.shape == (2, 2)


class TestGridVector2D:
    def test_to_xarray_returns_u_v_dataset(self):
        grid = GridVector2D(
            u_datas=np.ones((2, 3)),
            v_datas=np.zeros((2, 3)),
            start_lat=0, end_lat=10, lat_count=2,
            start_lon=100, end_lon=120, lon_count=3,
            lats=[], lons=[],
            u_element_name="U10", v_element_name="V10",
        )
        ds = read(grid).to_xarray()
        assert isinstance(ds, xr.Dataset)
        assert set(ds.data_vars) == {"U10", "V10"}
        assert ds["U10"].sizes == {"latitude": 2, "longitude": 3}
        assert ds["V10"].sum() == 0.0

    def test_default_var_names(self):
        grid = GridVector2D(
            u_datas=np.ones((1, 1)), v_datas=np.ones((1, 1)),
            start_lat=0, end_lat=0, lat_count=1,
            start_lon=0, end_lon=0, lon_count=1,
            lats=[], lons=[],
        )
        ds = read(grid).to_xarray()
        assert set(ds.data_vars) == {"u", "v"}


class TestArray2D:
    def test_to_pandas(self):
        array = Array2D(
            data=np.array([[1.0, 2.0], [3.0, 4.0]]),
            element_names=["TEM", "RHU"],
            row_count=2, col_count=2,
        )
        df = read(array).to_pandas()
        assert isinstance(df, pd.DataFrame)
        assert df.columns.tolist() == ["TEM", "RHU"]
        assert df.shape == (2, 2)

    def test_to_xarray_not_supported(self):
        array = Array2D(
            data=np.array([[1.0]]), element_names=["TEM"],
            row_count=1, col_count=1,
        )
        with pytest.raises(NotImplementedError, match="to_xarray"):
            read(array).to_xarray()


class TestMemoryReaderFactory:
    def test_claims_cmadaas_objects(self, grid_array):
        assert isinstance(MEMORY_READER(None, grid_array), CmadaasReader)

    def test_ignores_other_objects(self):
        assert MEMORY_READER(None, np.zeros(3)) is None
        assert MEMORY_READER(None, "not a response") is None
