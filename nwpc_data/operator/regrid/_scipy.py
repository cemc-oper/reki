import numpy as np
import xarray as xr
from scipy.interpolate import (
    interpn,
    RectBivariateSpline
)

from ._interpolator import (
    BaseInterpolator,
    _create_data_array
)


class ScipyInterpnInterpolator(BaseInterpolator):
    def __init__(
            self,
            method: str,
            **kwargs
    ):
        self.method = method
        self.kwargs = kwargs

    def interpolate_grid(
            self,
            data: xr.DataArray,
            target: xr.DataArray,
    ) -> xr.DataArray:
        latitudes = data.latitude.values
        longitudes = data.longitude.values

        values = data.values

        target_latitudes = target.latitude.values
        target_longitudes = target.longitude.values

        target_x, target_y = np.meshgrid(
            target_longitudes,
            target_latitudes,
        )

        target_values = interpn(
            (latitudes[::-1], longitudes),
            values[::-1, :],
            (target_x, target_y),
            method=self.method,
            **self.kwargs
        )

        target_field =_create_data_array(
            data=data,
            target=target,
            target_values=target_values
        )

        return target_field


class ScipyRectBivariateSplineInterpolator(BaseInterpolator):
    def __init__(
            self,
            method: str,
            **kwargs
    ):
        self.method = method
        self.kwargs = kwargs

    def interpolate_grid(
            self,
            data: xr.DataArray,
            target: xr.DataArray,
    ) -> xr.DataArray:
        latitudes = data.latitude.values
        longitudes = data.longitude.values

        values = data.values

        target_latitudes = target.latitude.values
        target_longitudes = target.longitude.values

        rbs = RectBivariateSpline(
            latitudes[::-1],
            longitudes,
            values[::-1, :],
            **self.kwargs
        )

        target_values = rbs(
            target_latitudes[::-1],
            target_longitudes
        )[::-1, :]

        target_field =_create_data_array(
            data=data,
            target=target,
            target_values=target_values
        )

        return target_field
