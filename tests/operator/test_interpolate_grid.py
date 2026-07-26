"""Tests for reki.operator.interpolate_grid.

The synthetic field is ``2*lat + lon``, so the linear scheme is exact
and spline schemes are near-exact.
"""

import numpy as np
import pytest

from reki.operator import interpolate_grid


def _expected_values(field):
    return (
        2.0 * field.latitude.values[:, None]
        + field.longitude.values[None, :]
    )


class TestLinearScheme:
    @pytest.mark.parametrize("engine", ["xarray", "scipy"])
    def test_values_are_exact(self, field, target_grid, engine):
        result = interpolate_grid(
            field, target_grid, scheme="linear", engine=engine,
        )
        assert result.shape == (
            target_grid.sizes["latitude"], target_grid.sizes["longitude"],
        )
        np.testing.assert_allclose(
            result.latitude.values, target_grid.latitude.values,
        )
        np.testing.assert_allclose(
            result.longitude.values, target_grid.longitude.values,
        )
        np.testing.assert_allclose(
            result.values, _expected_values(result), atol=1e-8,
        )

    @pytest.mark.parametrize("engine", ["xarray", "scipy"])
    def test_result_is_dataarray_with_coords(self, field, target_grid, engine):
        result = interpolate_grid(
            field, target_grid, scheme="linear", engine=engine,
        )
        assert result.dims == ("latitude", "longitude")
        assert "latitude" in result.coords
        assert "longitude" in result.coords


class TestOtherSchemes:
    def test_nearest_xarray(self, field, target_grid):
        result = interpolate_grid(
            field, target_grid, scheme="nearest", engine="xarray",
        )
        # nearest neighbour of a smooth field: error bounded by one grid step
        assert np.abs(result.values - _expected_values(result)).max() <= 2 * 10.0 + 5.0

    def test_nearest_scipy(self, field, target_grid):
        result = interpolate_grid(
            field, target_grid, scheme="nearest", engine="scipy",
        )
        assert np.abs(result.values - _expected_values(result)).max() <= 2 * 10.0 + 5.0

    @pytest.mark.parametrize("scheme", ["splinef2d", "rect_bivariate_spline"])
    def test_spline_schemes(self, field, target_grid, scheme):
        result = interpolate_grid(
            field, target_grid, scheme=scheme, engine="scipy",
        )
        np.testing.assert_allclose(
            result.values, _expected_values(result), atol=1e-4,
        )


class TestInvalidArguments:
    def test_unknown_scheme_for_engine(self, field, target_grid):
        with pytest.raises(ValueError, match="not supported"):
            interpolate_grid(
                field, target_grid, scheme="cubic", engine="scipy",
            )

    def test_unknown_engine(self, field, target_grid):
        with pytest.raises(ValueError, match="engine"):
            interpolate_grid(
                field, target_grid, scheme="linear", engine="no-such-engine",
            )
