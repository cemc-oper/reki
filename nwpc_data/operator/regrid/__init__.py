from typing import Dict, Union

import xarray as xr

from ._interpolator import _get_interpolator


def interpolate_grid(
        data: xr.DataArray,
        target: xr.DataArray,
        scheme: str = "linear",
        engine: str = "scipy",
        **kwargs: Dict,
) -> xr.DataArray:
    """

    Parameters
    ----------
    data
    target
    scheme: str
        interpolate method.
    engine: str
        interpolate engine, `scipy` or `xarray`
    kwargs

    Returns
    -------
    xr.DataArray
    """
    interpolator = _get_interpolator(scheme, engine, **kwargs)

    target_field = interpolator.interpolate_grid(
        data=data,
        target=target,
    )

    return target_field


def extract_point(
        data: xr.DataArray,
        latitude: Union[float, int],
        longitude: Union[float, int],
        scheme: str = "linear",
        engine: str = "xarray",
        **kwargs
) -> xr.DataArray:
    """

    Parameters
    ----------
    data
    latitude
    longitude
    scheme
    engine
    kwargs

    Returns
    -------
    xr.DataArray
    """
    interpolator = _get_interpolator(scheme, engine, **kwargs)
    value = interpolator.extract_point(data, latitude=latitude, longitude=longitude)
    return value
