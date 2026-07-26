"""Input handling for operator functions.

All public operator functions accept an ``xarray.DataArray`` as their
data argument — i.e. the object returned by
``reki.from_source(...).to_xarray()``.

This module is the single place where operator inputs are validated. It
is the reserved extension point for a future ``FieldList`` data object:
support for new input types (numpy array / FieldList) will be added here
as a dispatch layer (the earthkit-meteo array/xarray/fieldlist pattern)
without changing the public operator signatures.
"""

from typing import Any

import xarray as xr


def as_data_array(data: Any, arg_name: str = "data") -> xr.DataArray:
    """Validate that ``data`` is a gridded ``xarray.DataArray``.

    Parameters
    ----------
    data
        input data, must be an ``xarray.DataArray`` with 1D ``latitude``
        and ``longitude`` coordinates.
    arg_name
        argument name used in error messages.

    Returns
    -------
    xr.DataArray
        ``data`` itself, unchanged.

    Raises
    ------
    TypeError
        if ``data`` is not an ``xarray.DataArray``.
    ValueError
        if ``data`` has no 1D ``latitude``/``longitude`` coordinates.
    """
    if not isinstance(data, xr.DataArray):
        hint = ""
        if isinstance(data, xr.Dataset):
            hint = " Select a single variable first, e.g. ds['t']."
        elif hasattr(type(data), "to_xarray"):
            # NOTE: check the type, not the instance — a LazySource
            # forwards attribute access and hasattr() on the instance
            # would trigger the deferred remote request.
            hint = " Call .to_xarray() first, e.g. from_source(...).to_xarray()."
        raise TypeError(
            f"operator argument '{arg_name}' must be an xarray.DataArray, "
            f"got {type(data).__name__}.{hint}"
        )

    for coord_name in ("latitude", "longitude"):
        if coord_name not in data.coords:
            raise ValueError(
                f"operator argument '{arg_name}' must have a '{coord_name}' "
                f"coordinate, got coords: {list(data.coords)}"
            )
        if data.coords[coord_name].ndim != 1:
            raise ValueError(
                f"operator argument '{arg_name}' requires 1D '{coord_name}' "
                f"coordinates; curvilinear (2D) grids are not supported."
            )

    return data
