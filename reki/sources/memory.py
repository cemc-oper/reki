"""In-memory objects wrapped as a source."""

import numpy as np
import pandas as pd
import xarray as xr

from reki.core import Source


class MemorySource(Source):
    """Wrap an in-memory object as a source.

    Supports ``xarray.DataArray``, ``xarray.Dataset``,
    ``pandas.DataFrame`` and ``numpy.ndarray``. The source mutates to
    itself and only provides conversions between these representations.

    Parameters
    ----------
    buf
        the in-memory object to wrap.
    """

    def __init__(self, buf, **kwargs):
        super().__init__(**kwargs)
        if not isinstance(buf, (xr.DataArray, xr.Dataset, pd.DataFrame, np.ndarray)):
            raise TypeError(
                f"memory source does not support object of type {type(buf).__name__}"
            )
        self._buf = buf

    def mutate(self):
        return self

    def to_xarray(self, **kwargs):
        if isinstance(self._buf, (xr.DataArray, xr.Dataset)):
            return self._buf
        if isinstance(self._buf, pd.DataFrame):
            return self._buf.to_xarray()
        return xr.DataArray(self._buf, **kwargs)

    def to_pandas(self, **kwargs):
        if isinstance(self._buf, pd.DataFrame):
            return self._buf
        if isinstance(self._buf, xr.DataArray):
            return self._buf.to_pandas()
        if isinstance(self._buf, xr.Dataset):
            return self._buf.to_dataframe()
        if self._buf.ndim == 1:
            return pd.Series(self._buf, **kwargs)
        if self._buf.ndim == 2:
            return pd.DataFrame(self._buf, **kwargs)
        raise ValueError(
            f"cannot convert {self._buf.ndim}-dimensional ndarray to pandas"
        )

    def to_numpy(self, **kwargs):
        if isinstance(self._buf, np.ndarray):
            return self._buf
        if isinstance(self._buf, xr.Dataset):
            return self._buf.to_array().to_numpy()
        if isinstance(self._buf, (xr.DataArray, pd.DataFrame)):
            return self._buf.to_numpy()
        raise TypeError(
            f"cannot convert object of type {type(self._buf).__name__} to numpy"
        )


source = MemorySource
