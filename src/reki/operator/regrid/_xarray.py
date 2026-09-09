from typing import Union, Literal

import xarray as xr

from ._interpolator import BaseInterpolator


class XarrayInterpolator(BaseInterpolator):
    def __init__(
            self,
            method: Literal["linear", "nearest"],
            **kwargs
    ):
        self.method = method
        self.kwargs = kwargs

    def interpolate_grid(
            self,
            data,
            target
    ) -> xr.DataArray:
        target_field = data.interp_like(
            target,
            method=self.method,
            **self.kwargs
        )

        return target_field

    def extract_point(
            self,
            data: xr.DataArray,
            latitude: Union[int, float],
            longitude: Union[int, float],
    ) -> xr.DataArray:
        value = data.interp(
            latitude=latitude,
            longitude=longitude,
            method=self.method,
        )
        return value
