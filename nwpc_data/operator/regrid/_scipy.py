import typing

import numpy as np
from scipy.interpolate import (
    interpn,
    RectBivariateSpline
)

from ._interpolator import BaseInterpolator


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
            latitudes,
            longitudes,
            values: np.ndarray,
            target_latitudes,
            target_longitudes,
    ) -> np.ndarray:
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

        return target_values


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
            latitudes,
            longitudes,
            values: np.ndarray,
            target_latitudes,
            target_longitudes,
    ) -> np.ndarray:
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

        return target_values
