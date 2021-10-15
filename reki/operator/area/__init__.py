from typing import Union

import xarray as xr


def extract_region(
        data: xr.DataArray,
        start_longitude: Union[float, int],
        end_longitude: Union[float, int],
        start_latitude: Union[float, int],
        end_latitude: Union[float, int],
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

    Returns
    -------
    xr.DataArray
    """
    return data.sel(
        longitude=slice(start_longitude, end_longitude),
        latitude=slice(start_latitude, end_latitude)
    )
