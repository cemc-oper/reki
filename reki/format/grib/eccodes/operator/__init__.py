from typing import Union, Dict

import xarray as xr
import numpy as np
import eccodes

from reki.operator.area import extract_region as extract_region_field
from reki.operator.regrid import interpolate_grid as interpolate_grid_field
from reki.format.grib.eccodes._xarray import create_data_array_from_message
from reki.format.grib.common import MISSING_VALUE


def extract_region(
        message,
        start_longitude: Union[float, int],
        end_longitude: Union[float, int],
        start_latitude: Union[float, int],
        end_latitude: Union[float, int],
):
    """
    extract region from gridded data array.

    Parameters
    ----------
    message
    start_longitude
    end_longitude
    start_latitude
    end_latitude

    Returns
    -------
    """
    field = create_data_array_from_message(message)
    target_field = extract_region_field(
        field,
        start_longitude=start_longitude,
        end_longitude=end_longitude,
        start_latitude=start_latitude,
        end_latitude=end_latitude
    )

    eccodes.codes_set_double(message, 'longitudeOfFirstGridPointInDegrees', target_field.longitude.values[0])
    eccodes.codes_set_double(message, 'longitudeOfLastGridPointInDegrees', target_field.longitude.values[-1])
    # eccodes.codes_set_double(message, 'iDirectionIncrementInDegrees', self.grid.lon_step)
    eccodes.codes_set_long(message, 'Ni', len(target_field.longitude.values))

    eccodes.codes_set_double(message, 'latitudeOfFirstGridPointInDegrees', target_field.latitude.values[0])
    eccodes.codes_set_double(message, 'latitudeOfLastGridPointInDegrees', target_field.latitude.values[-1])
    # eccodes.codes_set_double(message, 'jDirectionIncrementInDegrees', self.grid.lat_step)
    eccodes.codes_set_long(message, 'Nj', len(target_field.latitude.values))

    eccodes.codes_set_double_array(message, "values", target_field.values.flatten())

    del field
    del target_field

    return message


def interpolate_grid(
        message,
        latitude,
        longitude,
        scheme: str = "linear",
        engine: str = "scipy",
        **kwargs: Dict,
):
    """

    Parameters
    ----------
    message
    latitude
    longitude
        interpolate method.
    scheme
    engine
        interpolate engine, `scipy` or `xarray`
    **kwargs

    Returns
    -------

    """
    target_grid = xr.DataArray(
        coords=[
            ("latitude", latitude),
            ("longitude", longitude)
        ]
    )

    missing_value = MISSING_VALUE
    field = create_data_array_from_message(
        message,
        missing_value=MISSING_VALUE,
        fill_missing_value=np.nan,
    )

    target_field = interpolate_grid_field(
        data=field,
        target=target_grid,
        scheme=scheme,
        engine=engine,
        **kwargs
    )

    eccodes.codes_set_double(message, 'longitudeOfFirstGridPointInDegrees', target_field.longitude.values[0])
    eccodes.codes_set_double(message, 'longitudeOfLastGridPointInDegrees', target_field.longitude.values[-1])
    eccodes.codes_set_double(message, 'iDirectionIncrementInDegrees', abs(target_field.longitude.values[0] - target_field.longitude.values[1]))
    eccodes.codes_set_long(message, 'Ni', len(target_field.longitude.values))

    eccodes.codes_set_double(message, 'latitudeOfFirstGridPointInDegrees', target_field.latitude.values[0])
    eccodes.codes_set_double(message, 'latitudeOfLastGridPointInDegrees', target_field.latitude.values[-1])
    eccodes.codes_set_double(message, 'jDirectionIncrementInDegrees', abs(target_field.latitude.values[0] - target_field.latitude.values[1]))
    eccodes.codes_set_long(message, 'Nj', len(target_field.latitude.values))

    values = target_field.values.flatten()

    eccodes.codes_set(message, 'missingValue', missing_value)
    num_missing = 0
    for i in range(len(values)):
        if values[i] == missing_value:
            num_missing += 1

    if num_missing > 0:
        eccodes.codes_set(message, 'bitmapPresent', 1)

    values = np.nan_to_num(values, missing_value)
    eccodes.codes_set_double_array(message, "values", values)

    if num_missing > 0:
        num_data = eccodes.codes_get(message, 'numberOfDataPoints', int)
        assert num_data == len(values)
        assert eccodes.codes_get(message, 'numberOfCodedValues', int) == num_data - num_missing
        assert eccodes.codes_get(message, 'numberOfMissing', int) == num_missing

    del field
    del target_field

    return message
