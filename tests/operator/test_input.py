"""Tests for operator input validation (reki.operator._dispatch)."""

import numpy as np
import pytest
import xarray as xr

import reki
from reki.operator import extract_point, extract_region, interpolate_grid
from reki.operator._dispatch import as_data_array

from .conftest import make_field, make_target_grid


class TestAsDataArray:
    def test_returns_dataarray_unchanged(self):
        field = make_field()
        assert as_data_array(field) is field

    def test_ndarray_raises_type_error(self):
        with pytest.raises(TypeError, match="xarray.DataArray"):
            as_data_array(np.zeros((3, 4)))

    def test_dataset_hint(self):
        dataset = make_field().to_dataset(name="t")
        with pytest.raises(TypeError, match=r"ds\['t'\]"):
            as_data_array(dataset)

    def test_reader_hint_uses_type_not_instance(self):
        class FakeReader:
            def to_xarray(self):
                return None

        with pytest.raises(TypeError, match="to_xarray"):
            as_data_array(FakeReader())

    def test_missing_latitude_coordinate(self):
        field = xr.DataArray(
            np.zeros((3, 4)),
            dims=("y", "x"),
            coords={"y": [1, 2, 3], "x": [1, 2, 3, 4]},
        )
        with pytest.raises(ValueError, match="latitude"):
            as_data_array(field)

    def test_2d_latitude_coordinate(self):
        field = xr.DataArray(
            np.zeros((3, 4)),
            dims=("y", "x"),
            coords={
                "latitude": (("y", "x"), np.zeros((3, 4))),
                "longitude": (("y", "x"), np.zeros((3, 4))),
            },
        )
        with pytest.raises(ValueError, match="1D"):
            as_data_array(field)


class TestPublicFunctionsValidateInput:
    def test_interpolate_grid_rejects_bad_data(self):
        with pytest.raises(TypeError, match="'data'"):
            interpolate_grid(np.zeros((3, 4)), make_target_grid())

    def test_interpolate_grid_rejects_bad_target(self):
        with pytest.raises(TypeError, match="'target'"):
            interpolate_grid(make_field(), np.zeros((3, 4)))

    def test_extract_point_rejects_bad_data(self):
        with pytest.raises(TypeError, match="'data'"):
            extract_point("not-a-field", latitude=0, longitude=0)

    def test_extract_region_rejects_bad_data(self):
        with pytest.raises(TypeError, match="'data'"):
            extract_region(None, 0, 1, 0, 1)


def test_operator_exposed_at_top_level():
    assert reki.operator.interpolate_grid is interpolate_grid
    assert reki.operator.extract_point is extract_point
    assert reki.operator.extract_region is extract_region
