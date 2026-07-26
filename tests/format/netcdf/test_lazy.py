"""Tests for NetCDF lazy loading (backend pass-through)."""

import numpy as np
import pytest
import xarray as xr

from reki.readers.netcdf import load_field_from_file


@pytest.fixture
def netcdf_file_path(tmp_path):
    rng = np.random.default_rng(42)
    dataset = xr.Dataset(
        {
            "t": (
                ("level", "latitude", "longitude"),
                rng.random((2, 3, 4)).astype(np.float64),
            ),
        },
        coords={
            "level": [850, 500],
            "latitude": [10.0, 11.0, 12.0],
            "longitude": [70.0, 71.0, 72.0, 73.0],
        },
    )
    file_path = tmp_path / "test.nc"
    dataset.to_netcdf(file_path)
    return file_path


def test_values_match_eager_read(netcdf_file_path):
    field = load_field_from_file(netcdf_file_path, parameter="t")
    expected = xr.open_dataset(netcdf_file_path)["t"]
    np.testing.assert_array_equal(field.values, expected.values)


def test_backend_is_lazy(netcdf_file_path):
    field = load_field_from_file(netcdf_file_path, parameter="t")
    # the backend reads from disk on demand instead of holding an
    # in-memory ndarray
    assert not isinstance(field.variable._data, np.ndarray)


def test_level_selection_stays_lazy(netcdf_file_path):
    field = load_field_from_file(
        netcdf_file_path, parameter="t", level_type="level", level=500,
    )
    assert not isinstance(field.variable._data, np.ndarray)
    expected = xr.open_dataset(netcdf_file_path)["t"].loc[{"level": 500}]
    np.testing.assert_array_equal(field.values, expected.values)


def test_kwargs_forwarded_to_open_dataset(netcdf_file_path):
    # engine is a valid open_dataset keyword and must be accepted
    field = load_field_from_file(
        netcdf_file_path, parameter="t", engine="scipy",
    )
    assert field.shape == (2, 3, 4)
