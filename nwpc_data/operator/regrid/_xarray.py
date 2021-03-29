import numpy as np
import xarray as xr

from ._interpolator import BaseInterpolator


class XarrayInterpolator(BaseInterpolator):
    def __init__(
            self,
            method: str,
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
