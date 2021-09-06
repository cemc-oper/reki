from typing import Union

import eccodes

from nwpc_data.operator.area import extract_region as extract_region_field
from nwpc_data.format.grib.eccodes._xarray import create_data_array_from_message


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
