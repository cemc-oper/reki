from typing import Union

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
            (target_y, target_x),
            method=self.method,
            **self.kwargs
        )

        target_field =_create_data_array(
            data=data,
            target=target,
            target_values=target_values
        )

        return target_field

    def extract_point(
            self,
            data: xr.DataArray,
            latitude: Union[float, int, list[Union[float, int]]],
            longitude: Union[float, int, list[Union[float, int]]],
    ) -> xr.DataArray:
        latitudes = data.latitude.values
        longitudes = data.longitude.values

        values = data.values

        if isinstance(latitude, list):
            target_latitudes = latitude
        else:
            target_latitudes = [latitude]
        if isinstance(longitude, list):
            target_longitudes = longitude
        else:
            target_longitudes = [longitude]

        target_x, target_y = np.meshgrid(
            target_longitudes,
            target_latitudes,
        )

        target_values = interpn(
            (latitudes[::-1], longitudes),
            values[::-1, :],
            (target_y, target_x),
            method=self.method,
            **self.kwargs
        )

        target_grid = xr.DataArray(
            np.zeros((len(target_latitudes), len(target_longitudes))),  # for xarray v0.10.3
            coords=[
                ("latitude", target_latitudes),
                ("longitude", target_longitudes)
            ],
        )

        target_field = _create_data_array(
            data=data,
            target=target_grid,
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

        if target_latitudes[0] > target_latitudes[-1]:
            target_values = rbs(
                target_latitudes[::-1],
                target_longitudes,
            )[::-1, :]
        else:
            target_values = rbs(
                target_latitudes,
                target_longitudes,
            )


        target_field =_create_data_array(
            data=data,
            target=target,
            target_values=target_values
        )

        return target_field

    def extract_point(
            self,
            data: xr.DataArray,
            latitude,
            longitude,
    ) -> xr.DataArray:
        latitudes = data.latitude.values
        longitudes = data.longitude.values

        values = data.values

        if isinstance(latitude, list):
            target_latitudes = latitude
        else:
            target_latitudes = [latitude]
        if isinstance(longitude, list):
            target_longitudes = longitude
        else:
            target_longitudes = [longitude]

        rbs = RectBivariateSpline(
            latitudes[::-1],
            longitudes,
            values[::-1, :],
            **self.kwargs
        )

        if target_latitudes[0] > target_latitudes[-1]:
            target_values = rbs(
                target_latitudes[::-1],
                target_longitudes,
            )[::-1, :]
        else:
            target_values = rbs(
                target_latitudes,
                target_longitudes,
            )

        target_grid = xr.DataArray(
            np.zeros((len(target_latitudes), len(target_longitudes))),  # for xarray v0.10.3
            coords=[
                ("latitude", target_latitudes),
                ("longitude", target_longitudes)
            ]
        )

        target_field = _create_data_array(
            data=data,
            target=target_grid,
            target_values=target_values
        )

        return target_field
