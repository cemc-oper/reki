"""Tests for reki.operator.extract_region."""

import numpy as np
import pytest

from reki.operator import extract_region


class TestSliceMode:
    def test_region_is_not_empty(self, field):
        # regression: descending latitude (e.g. GRIB output) used to
        # select an empty region
        region = extract_region(
            field,
            start_longitude=80, end_longitude=120,
            start_latitude=-10, end_latitude=30,
        )
        assert region.sizes["latitude"] > 0
        assert region.sizes["longitude"] > 0

    def test_region_bounds(self, field):
        region = extract_region(
            field,
            start_longitude=80, end_longitude=120,
            start_latitude=-10, end_latitude=30,
        )
        assert float(region.latitude.min()) >= -10
        assert float(region.latitude.max()) <= 30
        assert float(region.longitude.min()) >= 80
        assert float(region.longitude.max()) <= 120

    def test_region_values(self, field):
        region = extract_region(
            field,
            start_longitude=80, end_longitude=120,
            start_latitude=-10, end_latitude=30,
        )
        expected = (
            2.0 * region.latitude.values[:, None]
            + region.longitude.values[None, :]
        )
        np.testing.assert_allclose(region.values, expected, atol=1e-10)


class TestSteppedMode:
    def test_shape_and_coords(self, field):
        region = extract_region(
            field,
            start_longitude=80, end_longitude=120,
            start_latitude=-10, end_latitude=30,
            longitude_step=5.0, latitude_step=10.0,
        )
        assert region.sizes == {"latitude": 5, "longitude": 9}
        np.testing.assert_allclose(
            np.asarray(region.latitude), [-10, 0, 10, 20, 30],
        )
        np.testing.assert_allclose(
            np.asarray(region.longitude), np.arange(80, 121, 5.0),
        )

    def test_values_match_field(self, field):
        region = extract_region(
            field,
            start_longitude=80, end_longitude=120,
            start_latitude=-10, end_latitude=30,
            longitude_step=5.0, latitude_step=10.0,
        )
        value = region.sel(latitude=10.0, longitude=100.0)
        assert value.values.item() == pytest.approx(2 * 10.0 + 100.0)

    def test_single_step_raises(self, field):
        with pytest.raises(ValueError, match="together"):
            extract_region(
                field,
                start_longitude=80, end_longitude=120,
                start_latitude=-10, end_latitude=30,
                longitude_step=5.0,
            )
