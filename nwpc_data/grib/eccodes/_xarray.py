import typing
from pathlib import Path

import eccodes
import numpy as np
import xarray as xr

from nwpc_data.grib.eccodes._util import (
    _check_message
)


def load_field_from_file(
        file_path: str or Path,
        parameter: str or typing.Dict,
        level_type: str,
        level: int,
        **kwargs,
) -> xr.DataArray or None:
    with open(file_path, "rb") as f:
        while True:
            message_id = eccodes.codes_grib_new_from_file(f)
            if message_id is None:
                return None
            if not _check_message(message_id, parameter, level_type, level):
                eccodes.codes_release(message_id)
                continue

            data = create_xarray_array(message_id)
            eccodes.codes_release(message_id)
            return data
        return None


def create_xarray_array(message):
    values = eccodes.codes_get_double_array(message, "values")

    attr_keys = [
        'edition',
        'centre',
        'subCentre',
        'tablesVersion',
        "localTablesVersion",
        'dataType',
        'dataDate',
        'dataTime',
        'step',
        'stepType',
        'stepUnits',
        'stepRange',
        "name",
        "shortName",
        'cfName',
        'discipline',
        'parameterCategory',
        'parameterNumber',
        'shortName',
        'gridType',
        'gridDefinitionDescription',
        'typeOfFirstFixedSurface',
        'typeOfLevel',
        'level',
        'numberOfPoints',
        "missingValue",
        'units',
    ]

    grid_keys = [
        'latitudeOfFirstGridPointInDegrees',
        'longitudeOfFirstGridPointInDegrees',
        'latitudeOfLastGridPointInDegrees',
        'longitudeOfLastGridPointInDegrees',
        'iDirectionIncrementInDegrees',
        'jDirectionIncrementInDegrees',
        'Ni',
        'Nj',
    ]

    all_keys = attr_keys + grid_keys

    all_attrs = {}
    for key in all_keys:
        try:
            value = eccodes.codes_get(message, key)
        except:
            value = "undef"
        all_attrs[key] = value

    latitudeOfFirstGridPointInDegrees = all_attrs["latitudeOfFirstGridPointInDegrees"]
    longitudeOfFirstGridPointInDegrees = all_attrs["longitudeOfFirstGridPointInDegrees"]
    latitudeOfLastGridPointInDegrees = all_attrs["latitudeOfLastGridPointInDegrees"]
    longitudeOfLastGridPointInDegrees = all_attrs["longitudeOfLastGridPointInDegrees"]
    iDirectionIncrementInDegrees = all_attrs["iDirectionIncrementInDegrees"]
    jDirectionIncrementInDegrees = all_attrs["jDirectionIncrementInDegrees"]
    ni = all_attrs["Ni"]
    nj = all_attrs["Nj"]

    values = values.reshape(nj, ni)
    lons = np.linspace(longitudeOfFirstGridPointInDegrees, longitudeOfLastGridPointInDegrees, ni, endpoint=True)
    lats = np.linspace(latitudeOfFirstGridPointInDegrees, latitudeOfLastGridPointInDegrees, nj, endpoint=True)

    data = xr.DataArray(
        values,
        dims=("latitude", "longitude"),
        coords={
            "latitude": lats,
            "longitude": lons,
        }
    )

    data_attrs = {f"GRIB_{key}": all_attrs[key] for key in attr_keys if all_attrs[key] not in  ("undef", "unknown") }
    data.attrs = data_attrs

    if "GRIB_name" in data.attrs:
        data.attrs["long_name"] = data.attrs["GRIB_name"]
    else:
        name = (f"discipline={all_attrs['discipline']} "
                f"parmcat={all_attrs['parameterCategory']} "
                f"parm={all_attrs['parameterNumber']}")
        data.attrs["long_name"] = name

    if "GRIB_units" in data.attrs:
        data.attrs["units"] = data.attrs["GRIB_units"]
    return data
