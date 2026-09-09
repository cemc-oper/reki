"""Reader for CMADaaS MUSIC response objects (Grid*2D / Array2D).

This reader converts the in-memory response classes of ``nuwe-cmadaas``
into xarray/pandas objects. It never imports ``nuwe_cmadaas`` at module
level: ``nuwe-cmadaas`` is an optional dependency, and the reader
directory scan imports every reader module eagerly. Objects are
recognized by their class name instead.

.. note::

   ``GridArray2D.to_xarray()`` of nuwe-cmadaas (<= 0.3.0) assigns
   ``self.lats`` to the longitude coordinates when ``self.lons`` is
   given. Coordinates are therefore built here from
   ``start_*/end_*/count`` (or from correctly paired ``lats``/``lons``
   lists) instead of delegating to that method.
"""

import numpy as np
import pandas as pd
import xarray as xr

from reki.readers import Reader

#: nuwe-cmadaas response classes converted by to_xarray().
_GRID_CLASSES = ("GridArray2D", "GridScalar2D", "GridVector2D")
#: nuwe-cmadaas response classes converted by to_pandas().
_TABLE_CLASSES = ("Array2D",)

_COORD_ATTRS = {
    "latitude": {
        "units": "degrees_north",
        "standard_name": "latitude",
        "long_name": "latitude",
    },
    "longitude": {
        "units": "degrees_east",
        "standard_name": "longitude",
        "long_name": "longitude",
    },
}


def _grid_coords(grid):
    """Build (latitude, longitude) coordinate dict from a Grid*2D object."""
    if len(grid.lats) > 0:
        lats = np.asarray(grid.lats)
    else:
        lats = np.linspace(grid.start_lat, grid.end_lat, grid.lat_count)

    if len(grid.lons) > 0:
        lons = np.asarray(grid.lons)
    else:
        lons = np.linspace(grid.start_lon, grid.end_lon, grid.lon_count)

    return {
        "latitude": xr.Variable("latitude", lats, attrs=_COORD_ATTRS["latitude"]),
        "longitude": xr.Variable("longitude", lons, attrs=_COORD_ATTRS["longitude"]),
    }


def _grid_values(grid, data):
    """Return ``data`` as a 2-D (latitude, longitude) array."""
    values = np.asarray(data)
    if values.ndim == 1:
        values = values.reshape(grid.lat_count, grid.lon_count)
    return values


class CmadaasReader(Reader):
    """Convert a CMADaaS MUSIC response object to xarray/pandas."""

    def __init__(self, source, buf, **kwargs):
        super().__init__(source, f"<{type(buf).__name__}>")
        self.buf = buf

    def to_xarray(self, **kwargs):
        class_name = type(self.buf).__name__
        if class_name in ("GridArray2D", "GridScalar2D"):
            return self._scalar_to_xarray()
        if class_name == "GridVector2D":
            return self._vector_to_xarray()
        raise NotImplementedError(
            f"{type(self).__name__} does not support to_xarray() "
            f"for {class_name}"
        )

    def to_pandas(self, **kwargs):
        class_name = type(self.buf).__name__
        if class_name == "Array2D":
            return pd.DataFrame(self.buf.data, columns=self.buf.element_names)
        raise NotImplementedError(
            f"{type(self).__name__} does not support to_pandas() "
            f"for {class_name}"
        )

    def _scalar_to_xarray(self) -> xr.DataArray:
        grid = self.buf
        field = xr.DataArray(
            _grid_values(grid, grid.data),
            dims=("latitude", "longitude"),
            coords=_grid_coords(grid),
            attrs={"units": grid.units},
        )
        if grid.user_element_name:
            field.name = grid.user_element_name
        return field

    def _vector_to_xarray(self) -> xr.Dataset:
        grid = self.buf
        coords = _grid_coords(grid)
        dims = ("latitude", "longitude")
        u_name = grid.u_element_name or "u"
        v_name = grid.v_element_name or "v"
        return xr.Dataset(
            data_vars={
                u_name: xr.DataArray(
                    _grid_values(grid, grid.u_datas), dims=dims, coords=coords,
                ),
                v_name: xr.DataArray(
                    _grid_values(grid, grid.v_datas), dims=dims, coords=coords,
                ),
            }
        )


def MEMORY_READER(source, buf, **kwargs):
    """Claim nuwe-cmadaas response objects (recognized by class name)."""
    if type(buf).__name__ in _GRID_CLASSES + _TABLE_CLASSES:
        return CmadaasReader(source, buf, **kwargs)
    return None
