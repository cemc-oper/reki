import typing

import xarray as xr

from ._interpolator import _get_interpolator


def interpolate_grid(
        data: xr.DataArray,
        target: xr.DataArray,
        scheme: str = "linear",
        engine: str = "scipy",
        **kwargs: typing.Dict,
) -> xr.DataArray:
    """

    Parameters
    ----------
    data
    target
    scheme
    kwargs

    Returns
    -------

    """



    interpolator = _get_interpolator(scheme, engine, **kwargs)

    target_field = interpolator.interpolate_grid(
        data=data,
        target=target,
    )

    return target_field
