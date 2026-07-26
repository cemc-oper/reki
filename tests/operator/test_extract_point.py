"""Tests for reki.operator.extract_point."""

import numpy as np
import pytest

from reki.operator import extract_point

ENGINES_AND_SCHEMES = [
    ("xarray", "linear"),
    ("xarray", "nearest"),
    ("scipy", "linear"),
    ("scipy", "nearest"),
    ("scipy", "splinef2d"),
    ("scipy", "rect_bivariate_spline"),
]


class TestSinglePoint:
    @pytest.mark.parametrize("engine", ["xarray", "scipy"])
    def test_linear_scheme_is_exact(self, field, engine):
        # the field is 2*lat + lon: linear interpolation is exact
        point = extract_point(
            field, latitude=12.3, longitude=99.7, scheme="linear", engine=engine,
        )
        assert point.values.item() == pytest.approx(2 * 12.3 + 99.7, abs=1e-6)

    @pytest.mark.parametrize("engine,scheme", ENGINES_AND_SCHEMES)
    def test_point_coordinates(self, field, engine, scheme):
        point = extract_point(
            field, latitude=12.3, longitude=99.7, scheme=scheme, engine=engine,
        )
        assert np.asarray(point.latitude).item() == pytest.approx(12.3)
        assert np.asarray(point.longitude).item() == pytest.approx(99.7)


class TestMultiplePoints:
    @pytest.mark.parametrize("engine,scheme", ENGINES_AND_SCHEMES)
    def test_shape_and_coords(self, field, engine, scheme):
        point = extract_point(
            field,
            latitude=[40, 39],
            longitude=[115, 116, 117],
            scheme=scheme,
            engine=engine,
        )
        assert point.shape == (2, 3)
        assert list(np.asarray(point.latitude)) == [40, 39]
        assert list(np.asarray(point.longitude)) == [115, 116, 117]

    @pytest.mark.parametrize("engine", ["xarray", "scipy"])
    def test_linear_values_on_grid_points(self, field, engine):
        point = extract_point(
            field,
            latitude=[0, 10],
            longitude=[100, 110],
            scheme="linear",
            engine=engine,
        )
        # grid points are reproduced exactly
        expected = np.array(
            [[2 * lat + lon for lon in [100, 110]] for lat in [0, 10]],
            dtype=float,
        )
        np.testing.assert_allclose(point.values, expected, atol=1e-8)
