"""Tests for reki.operator.sample_nearest."""

import numpy as np
import pytest

from reki.operator import sample_nearest


class TestStrideSampling:
    def test_shape_and_coords(self, field):
        # data grid: latitude step 10°, longitude step 5°
        sampled = sample_nearest(field, longitude_step=10.0, latitude_step=20.0)
        assert sampled.sizes == {"latitude": 5, "longitude": 9}
        np.testing.assert_allclose(
            np.sort(np.asarray(sampled.latitude)), np.arange(-40, 41, 20.0),
        )
        np.testing.assert_allclose(
            np.asarray(sampled.longitude), np.arange(60, 141, 10.0),
        )

    def test_values_match_field(self, field):
        sampled = sample_nearest(field, longitude_step=10.0, latitude_step=20.0)
        expected = (
            2.0 * sampled.latitude.values[:, None]
            + sampled.longitude.values[None, :]
        )
        np.testing.assert_allclose(sampled.values, expected, atol=1e-10)

    def test_output_grid_is_subset_of_input_grid(self, field):
        sampled = sample_nearest(field, longitude_step=15.0, latitude_step=30.0)
        assert set(np.asarray(sampled.latitude)).issubset(
            set(np.asarray(field.latitude))
        )
        assert set(np.asarray(sampled.longitude)).issubset(
            set(np.asarray(field.longitude))
        )

    def test_anchored_at_first_grid_point(self, field):
        sampled = sample_nearest(field, longitude_step=10.0, latitude_step=20.0)
        assert float(sampled.latitude.values[0]) == float(field.latitude.values[0])
        assert float(sampled.longitude.values[0]) == float(field.longitude.values[0])

    def test_ratio_is_rounded(self, field):
        # 12.0 / 5.0 = 2.4 -> stride 2; 24.0 / 10.0 = 2.4 -> stride 2
        sampled = sample_nearest(field, longitude_step=12.0, latitude_step=24.0)
        assert sampled.sizes == {"latitude": 5, "longitude": 9}

    def test_latitude_step_defaults_to_longitude_step(self, field):
        sampled = sample_nearest(field, longitude_step=20.0)
        assert sampled.sizes == {"latitude": 5, "longitude": 5}


class TestNoOp:
    def test_smaller_step_returns_input_unchanged(self, field):
        result = sample_nearest(field, longitude_step=1.0)
        assert result is field

    def test_equal_step_returns_input_unchanged(self, field):
        result = sample_nearest(field, longitude_step=5.0, latitude_step=10.0)
        assert result is field


class TestInputValidation:
    def test_non_dataarray_raises(self):
        with pytest.raises(TypeError, match="xarray.DataArray"):
            sample_nearest(np.zeros((3, 3)), longitude_step=1.0)
