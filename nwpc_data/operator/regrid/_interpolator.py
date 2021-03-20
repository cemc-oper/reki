import abc
import typing

import numpy as np


class BaseInterpolator(abc.ABC):
    @abc.abstractmethod
    def interpolate_grid(
            self,
            latitudes: np.ndarray,
            longitudes: np.ndarray,
            values: np.ndarray,
            target_latitudes: np.ndarray,
            target_longitudes: np.ndarray,
    ) -> np.ndarray:
        pass


def _get_interpolator(
        scheme: str,
        engine: str,
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
    else:
        raise ValueError(f"engine {engine} is not supported")
