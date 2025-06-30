from typing import Union, Optional

import xarray as xr
import numpy as np


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
    if longitude_step is None and latitude_step is None:
        return data.sel(
            longitude=slice(start_longitude, end_longitude),
            latitude=slice(start_latitude, end_latitude)
        )
    elif longitude_step is not None and latitude_step is not None:
        orig_lat_step = data.latitude[1] - data.latitude[0]
        orig_lon_step = data.longitude[1] - data.longitude[0]
        return data.sel(
            latitude=xr.DataArray(np.arange(start_latitude, end_latitude + orig_lat_step/10.0, latitude_step), dims="latitude"),
            longitude=xr.DataArray(np.arange(start_longitude, end_longitude + orig_lon_step/10.0, longitude_step), dims="longitude")
        )
    else:
        raise ValueError("longitude_step and latitude_step must be set together.")
