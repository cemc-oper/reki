import typing

import xarray as xr

from ._interpolator import _get_interpolator


def interpolate_grid(
        data: xr.DataArray,
        target: xr.DataArray,
        scheme: str = "linear",
        engine = None,
        **kwargs: typing.Dict,
) -> xr.DataArray:
    """

    Parameters
    ----------
    data
    target
    scheme
    engine

    Returns
    -------

    """

    latitudes = data.latitude.values
    longitudes = data.longitude.values

    values = data.values

    target_latitudes = target.latitude.values
    target_longitudes = target.longitude.values

    interpolator = _get_interpolator(scheme, **kwargs)

    target_values = interpolator.interpolate_grid(
        latitudes=latitudes,
        longitudes=longitudes,
        values=values,
        target_latitudes=target_latitudes,
        target_longitudes=target_longitudes,
    )

    coords = data.coords.to_dataset()
    coords["longitude"] = target["longitude"]
    coords["latitude"] = target["latitude"]

    target_field = xr.DataArray(
        target_values,
        coords=coords.coords,
        dims=data.dims
    )

    return target_field
