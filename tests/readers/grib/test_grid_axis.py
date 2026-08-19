"""Tests for ``_build_grid_axis``: regular axis construction from GRIB
grid definition keys, including global grids that wrap around the
prime meridian (e.g. ``first=180, last=179.75`` for a grid starting at
180°E ≡ 180°W heading east).
"""

import numpy as np

from reki.readers.grib.eccodes._xarray import _build_grid_axis


def test_plain_axis_uses_linspace():
    axis = _build_grid_axis(60.0, 150.0, 361, 0.25)
    assert axis[0] == 60.0
    assert axis[-1] == 150.0
    assert len(axis) == 361


def test_descending_axis():
    axis = _build_grid_axis(90.0, -90.0, 721, 0.25)
    assert axis[0] == 90.0
    assert axis[-1] == -90.0
    assert np.all(np.diff(axis) < 0)


def test_wrapping_global_longitude_is_normalized():
    # 180 -> 180.25 -> ... -> 359.75 -> 0 -> ... -> 179.75 (mod 360),
    # declared as first=180, last=179.75: rebuild from the increment and
    # normalize to [-180, 180).
    axis = _build_grid_axis(180.0, 179.75, 1440, 0.25, wrap=360.0)
    assert axis[0] == -180.0
    assert axis[-1] == 179.75
    assert np.all(np.diff(axis) > 0)


def test_non_wrapping_axis_starting_at_zero_unchanged():
    # 0 -> 359.75 does not wrap: last is consistent with the increment.
    axis = _build_grid_axis(0.0, 359.75, 1440, 0.25, wrap=360.0)
    assert axis[0] == 0.0
    assert axis[-1] == 359.75
