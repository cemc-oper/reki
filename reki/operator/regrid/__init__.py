from typing import Union, Literal

import xarray as xr

from ._interpolator import _get_interpolator


def interpolate_grid(
        data: xr.DataArray,
        target: xr.DataArray,
        scheme: str = "linear",
        engine: Literal["scipy", "xarray"] = "xarray",
        **kwargs
) -> xr.DataArray:
    """
    Interpolate grid data into a target grid.

    Parameters
    ----------
    data : xr.DataArray
        intput data
    target : xr.DataArray
        target grid
    scheme : str
        interpolate method.

        * if ``engine="xarray"``, `linear` or `nearest`
        * if ``engine="scipy"``, `linear`, `nearest`, `splinef2d` or `rect_bivariate_spline`
    engine : str
        interpolate engine, `xarray` or `scipy`
    kwargs
        key-value parameters to be passed to interpolator with _get_interpolator function.

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
        latitude: Union[float, int, list[Union[float, int]]],
        longitude: Union[float, int, list[Union[float, int]]],
        scheme: str = "linear",
        engine: Literal["scipy", "xarray"] = "xarray",
        **kwargs
) -> xr.DataArray:
    """
    Extract a point from 2D field with interpolation.

    Parameters
    ----------
    data
    latitude
    longitude
    scheme
        interpolate method.

        * if ``engine="xarray"``, `linear` or `nearest`
        * if ``engine="scipy"``, `linear`, `nearest`, `splinef2d` or `rect_bivariate_spline`
    engine
        interpolate engine, `xarray` or `scipy`.
    kwargs

    Returns
    -------
    xr.DataArray
    """
    interpolator = _get_interpolator(scheme, engine, **kwargs)
    value = interpolator.extract_point(data, latitude=latitude, longitude=longitude)
    return value
