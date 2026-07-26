"""End-to-end tests: from_source().to_xarray() output feeds operators.

Uses the real GRIB2 test file (fetched through the ``test`` source via
the root conftest fixture). GRIB fields come with descending latitude,
which is the orientation the operators had to adapt to (Phase 8).
"""

import numpy as np
import pytest
import xarray as xr

import reki
from reki.operator import extract_point, extract_region, interpolate_grid


@pytest.fixture
def field(grib2_gfs_basic_file_path) -> xr.DataArray:
    data = reki.from_source("file", grib2_gfs_basic_file_path).to_xarray(
        parameter="t", level_type="pl", level=850,
    )
    assert isinstance(data, xr.DataArray)
    return data


@pytest.fixture
def region_bounds(field):
    """A small region well inside the field's domain."""
    lats = np.sort(field.latitude.values)
    lons = np.sort(field.longitude.values)
    return {
        "start_latitude": float(lats[len(lats) // 2 - 5]),
        "end_latitude": float(lats[len(lats) // 2 + 5]),
        "start_longitude": float(lons[len(lons) // 2 - 5]),
        "end_longitude": float(lons[len(lons) // 2 + 5]),
    }


def test_extract_region(field, region_bounds):
    region = extract_region(field, **region_bounds)
    assert region.sizes["latitude"] > 0
    assert region.sizes["longitude"] > 0
    assert float(region.latitude.min()) >= region_bounds["start_latitude"]
    assert float(region.latitude.max()) <= region_bounds["end_latitude"]
    assert np.isfinite(region.values).all()


def test_extract_point(field, region_bounds):
    latitude = (region_bounds["start_latitude"] + region_bounds["end_latitude"]) / 2
    longitude = (region_bounds["start_longitude"] + region_bounds["end_longitude"]) / 2
    for engine in ("xarray", "scipy"):
        point = extract_point(
            field, latitude=latitude, longitude=longitude, engine=engine,
        )
        assert np.isfinite(point.values).all()


def test_interpolate_grid(field, region_bounds):
    target = xr.DataArray(
        coords=[
            ("latitude", np.arange(
                region_bounds["start_latitude"],
                region_bounds["end_latitude"] + 1.0, 1.0,
            )),
            ("longitude", np.arange(
                region_bounds["start_longitude"],
                region_bounds["end_longitude"] + 1.0, 1.0,
            )),
        ]
    )
    for engine in ("xarray", "scipy"):
        result = interpolate_grid(field, target, scheme="linear", engine=engine)
        assert result.shape == (target.sizes["latitude"], target.sizes["longitude"])
        assert np.isfinite(result.values).all()


class TestLazyField:
    """Operators consume lazy fields: decoding happens on data access."""

    @pytest.fixture
    def lazy_field(self, grib2_gfs_basic_file_path) -> xr.DataArray:
        return reki.from_source("file", grib2_gfs_basic_file_path).to_xarray(
            parameter="t", level_type="pl", level=850, lazy=True,
        )

    def test_extract_region_matches_eager(self, lazy_field, field, region_bounds):
        lazy_region = extract_region(lazy_field, **region_bounds)
        eager_region = extract_region(field, **region_bounds)
        np.testing.assert_array_equal(lazy_region.values, eager_region.values)

    def test_extract_point_matches_eager(self, lazy_field, field, region_bounds):
        latitude = (region_bounds["start_latitude"] + region_bounds["end_latitude"]) / 2
        longitude = (region_bounds["start_longitude"] + region_bounds["end_longitude"]) / 2
        lazy_point = extract_point(lazy_field, latitude=latitude, longitude=longitude)
        eager_point = extract_point(field, latitude=latitude, longitude=longitude)
        assert lazy_point.values.item() == pytest.approx(eager_point.values.item())
