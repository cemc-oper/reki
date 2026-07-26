from typing import Union, Optional

import xarray as xr
import numpy as np

from .._dispatch import as_data_array


def extract_region(
        data: xr.DataArray,
        start_longitude: Union[float, int],
        end_longitude: Union[float, int],
        start_latitude: Union[float, int],
        end_latitude: Union[float, int],
        longitude_step: Optional[Union[float, int]] = None,
        latitude_step: Optional[Union[float, int]] = None,
) -> xr.DataArray:
    """
    extract region from gridded data array.

    Parameters
    ----------
    data
    start_longitude
    end_longitude
    start_latitude
    end_latitude
    longitude_step
    latitude_step

    Returns
    -------
    xr.DataArray
    """
    as_data_array(data, arg_name="data")

    # GRIB fields are usually stored with descending latitude (90 -> -90)
    # while other sources may be ascending; pick the slice direction that
    # matches the input coordinate order.
    latitudes = data.latitude.values
    if latitudes[0] <= latitudes[-1]:
        latitude_slice = slice(start_latitude, end_latitude)
    else:
        latitude_slice = slice(end_latitude, start_latitude)

    if longitude_step is None and latitude_step is None:
        return data.sel(
            longitude=slice(start_longitude, end_longitude),
            latitude=latitude_slice
        )
    elif longitude_step is not None and latitude_step is not None:
        orig_lat_step = abs(data.latitude.values[1] - data.latitude.values[0])
        orig_lon_step = abs(data.longitude.values[1] - data.longitude.values[0])
        # pointwise selection: works regardless of coordinate order, and
        # the result latitude follows the ascending target values.
        return data.sel(
            latitude=xr.DataArray(np.arange(start_latitude, end_latitude + orig_lat_step/10.0, latitude_step), dims="latitude"),
            longitude=xr.DataArray(np.arange(start_longitude, end_longitude + orig_lon_step/10.0, longitude_step), dims="longitude")
        )
    else:
        raise ValueError("longitude_step and latitude_step must be set together.")
