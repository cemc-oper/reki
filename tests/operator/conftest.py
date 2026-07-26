"""Shared fixtures for operator tests.

The synthetic field is the analytic function ``values = 2*lat + lon`` on
a regular grid, so linear interpolation reproduces target values exactly
and assertions can be strict.
"""

import numpy as np
import pytest
import xarray as xr


def make_field(ascending: bool = True) -> xr.DataArray:
    """A 2D field on a 10° x 5° grid: values = 2*latitude + longitude."""
    latitudes = np.arange(-40, 41, 10.0)
    if not ascending:
        latitudes = latitudes[::-1]
    longitudes = np.arange(60, 141, 5.0)
    lon2d, lat2d = np.meshgrid(longitudes, latitudes)
    return xr.DataArray(
        2.0 * lat2d + lon2d,
        dims=("latitude", "longitude"),
        coords={"latitude": latitudes, "longitude": longitudes},
        name="t",
    )


def make_target_grid() -> xr.DataArray:
    """A finer target grid inside the synthetic field's domain."""
    return xr.DataArray(
        coords=[
            ("latitude", np.arange(-20, 21, 2.0)),
            ("longitude", np.arange(70, 131, 5.0)),
        ]
    )


@pytest.fixture(params=[True, False], ids=["ascending", "descending"])
def field(request) -> xr.DataArray:
    """The synthetic field, with both latitude coordinate orders."""
    return make_field(ascending=request.param)


@pytest.fixture
def target_grid() -> xr.DataArray:
    return make_target_grid()
