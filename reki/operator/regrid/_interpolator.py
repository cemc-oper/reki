import abc
from typing import Union, Literal

import numpy as np
import xarray as xr


class BaseInterpolator(abc.ABC):
    @abc.abstractmethod
    def interpolate_grid(
            self,
            data: xr.DataArray,
            target: xr.DataArray,
    ) -> xr.DataArray:
        pass

    @abc.abstractmethod
    def extract_point(
            self,
            data: xr.DataArray,
            latitude: Union[int, float],
            longitude: Union[int, float],
    ) -> xr.DataArray:
        pass


def _get_interpolator(
        scheme: str,
        engine: Literal["scipy", "xarray"],
        **kwargs
) -> BaseInterpolator:
    if engine == "scipy":
        from ._scipy import ScipyInterpnInterpolator, ScipyRectBivariateSplineInterpolator
        if scheme in ["linear", "nearest", "splinef2d"]:
            return ScipyInterpnInterpolator(scheme, **kwargs)
        elif scheme in ["rect_bivariate_spline"]:
            return ScipyRectBivariateSplineInterpolator(scheme, **kwargs)
        else:
            raise ValueError(f"{scheme} is not supported for engine {engine}")
    elif engine == "xarray":
        from ._xarray import XarrayInterpolator
        return XarrayInterpolator(scheme, **kwargs)
    else:
        raise ValueError(f"engine {engine} is not supported")


def _create_data_array(
        data: xr.DataArray,
        target: xr.DataArray,
        target_values: np.ndarray,
) -> xr.DataArray:
    coords = data.coords.to_dataset()
    coords["longitude"] = target["longitude"]
    coords["latitude"] = target["latitude"]

    target_field = xr.DataArray(
        target_values,
        coords=coords.coords,
        dims=data.dims
    )
    return target_field
