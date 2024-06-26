from typing import Dict, Optional, Union, Tuple
import math

import numpy as np
import xarray as xr
import pandas as pd

import eccodes

from reki.format.grib.common import MISSING_VALUE

# from loguru import logger


def create_data_array_from_message(
        message,
        level_dim_name: Optional[str] = None,
        field_name: Optional[str] = None,
        missing_value: Optional[float] = None,
        fill_missing_value: Optional = np.nan,
        values: Optional[np.ndarray] = None,
) -> xr.DataArray:
    """
    Create ``xarray.DataArray`` from one GRIB2 message.

    Parameters
    ----------
    message
        grib message id loaded by ecCodes python API.
    level_dim_name
    field_name
    missing_value
        set missingValue key in GRIB message before get array.
        If set None, use MISSING_VALUE set in common module.
        NOTE: ecCodes use 9999 as default missing value.
    fill_missing_value
        filled value to replace missing value point in array.
        default is np.nan.
        If set None, missing value will not be changed.
    values
        message values. if None, function will decode values from message.
        if set, function will use values instead of decode message.
    """
    if missing_value is None:
        missing_value = MISSING_VALUE
    eccodes.codes_set(message, "missingValue", missing_value)

    if values is None:
        # logger.info("decoding...")
        values = eccodes.codes_get_double_array(message, "values")
        # logger.info("decoding...done")

    if fill_missing_value is not None:
        np.place(values, values == missing_value, fill_missing_value)

    attr_keys = [
        'edition',
        'centre',
        'subCentre',
        'tablesVersion',
        "localTablesVersion",
        'dataType',
        'dataDate',
        'dataTime',
        'validityDate',
        'validityTime',
        'step',
        'stepType',
        'stepUnits',
        'stepRange',
        'endStep:int',
        'count'
    ]

    parameter_keys = [
        "name",
        "shortName",
        'cfName',
        'discipline',
        'parameterCategory',
        'parameterNumber',
        'units',
    ]

    grid_keys = [
        'gridType',
        'gridDefinitionDescription',
        'numberOfPoints',
        "missingValue",
        'latitudeOfFirstGridPointInDegrees',
        'longitudeOfFirstGridPointInDegrees',
        'latitudeOfLastGridPointInDegrees',
        'longitudeOfLastGridPointInDegrees',
        'iDirectionIncrementInDegrees',
        'jDirectionIncrementInDegrees',
        'Ni',
        'Nj',
    ]

    level_keys = [
        'typeOfLevel',
        'level',
        "typeOfFirstFixedSurface",
        "typeOfSecondFixedSurface",
        "scaleFactorOfFirstFixedSurface",
        "scaledValueOfFirstFixedSurface",
        "scaleFactorOfSecondFixedSurface",
        "scaledValueOfSecondFixedSurface",
    ]

    all_keys = attr_keys + parameter_keys + grid_keys + level_keys

    all_attrs = {}
    key_type_mapper = {
        "int": int,
        "float": float,
        "str": str,
    }
    for key in all_keys:
        tokens = key.split(":")
        if len(tokens) == 1:
            try:
                value = eccodes.codes_get(message, key)
            except:
                value = "undef"
        elif len(tokens) == 2:
            key_name = tokens[0]
            key_type = key_type_mapper[tokens[1]]
            try:
                value = eccodes.codes_get(message, key_name, key_type)
            except:
                value = "undef"
        else:
            value = "undef"
        all_attrs[key] = value

    latitude_of_first_grid_point_in_degrees = all_attrs["latitudeOfFirstGridPointInDegrees"]
    longitude_of_first_grid_point_in_degrees = all_attrs["longitudeOfFirstGridPointInDegrees"]
    latitude_of_last_grid_point_in_degrees = all_attrs["latitudeOfLastGridPointInDegrees"]
    longitude_of_last_grid_point_in_degrees = all_attrs["longitudeOfLastGridPointInDegrees"]
    ni = all_attrs["Ni"]
    nj = all_attrs["Nj"]

    values = values.reshape(nj, ni)
    lons = np.linspace(
        longitude_of_first_grid_point_in_degrees, longitude_of_last_grid_point_in_degrees, ni,
        endpoint=True
    )
    lats = np.linspace(
        latitude_of_first_grid_point_in_degrees, latitude_of_last_grid_point_in_degrees, nj,
        endpoint=True
    )

    # coords
    coords = {}

    # add time and step coordinate
    time_name, value = get_time_from_attrs(all_attrs)
    coords[time_name] = value

    step_name, value = get_step_from_attrs(all_attrs)
    coords[step_name] = value

    # add valid time coordinate
    valid_time_name, value = get_valid_time_from_attrs(all_attrs)
    if valid_time_name is not None:
        coords[valid_time_name] = value

    # add level coordinate
    level_name, value = get_level_from_attrs(all_attrs, level_dim_name)
    coords[level_name] = value

    coords["latitude"] = xr.Variable(
        "latitude",
        lats,
        attrs={
            "units": "degrees_north",
            "standard_name": "latitude",
            "long_name": "latitude"
        },
    )
    coords["longitude"] = xr.Variable(
        "longitude",
        lons,
        attrs={
            "units": "degrees_east",
            "standard_name": "longitude",
            "long_name": "longitude"
        }
    )

    #   check ENS
    key_name = "perturbationNumber"
    try:
        value = eccodes.codes_get(message, key_name)
    except:
        value = None
    if value is not None:
        coords["number"] = value

    dims = ("latitude", "longitude")

    data_attrs = {f"GRIB_{key}": all_attrs[key] for key in attr_keys if all_attrs[key] not in ("undef", "unknown")}

    # set long_name
    if "GRIB_name" in data_attrs:
        data_attrs["long_name"] = data_attrs["GRIB_name"]
    else:
        name = (f"discipline={all_attrs['discipline']} "
                f"parmcat={all_attrs['parameterCategory']} "
                f"parm={all_attrs['parameterNumber']}")
        data_attrs["long_name"] = name

    # set name
    if field_name is not None:
        var_name = field_name
    elif "shortName" in all_attrs and all_attrs["shortName"] != "unknown":
        var_name = all_attrs["shortName"]
    else:
        var_name = f"{all_attrs['discipline']}_{all_attrs['parameterCategory']}_{all_attrs['parameterNumber']}"

    # set units
    if "GRIB_units" in data_attrs:
        data_attrs["units"] = data_attrs["GRIB_units"]

    data = xr.DataArray(
        values,
        dims=dims,
        coords=coords,
        attrs=data_attrs,
        name=var_name,
    )

    return data


def get_level_coordinate_name(data: xr.DataArray) -> Optional[str]:
    """
    Get coordinate name from ``xarray.DataArray`` object.

    NOTE: please use typeOfLevel if available and don't use this function.

    Parameters
    ----------
    data: xr.DataArray

    Returns
    -------
    str or None
    """
    coords = data.coords
    for coord in coords:
        if coord.startswith("level_"):
            return coord
    return None


def get_time_from_attrs(all_attrs):
    start_time = pd.to_datetime(
        f"{all_attrs['dataDate']}{all_attrs['dataTime']:04}",
        format="%Y%m%d%H%M"
    )
    return "time", start_time


def get_step_from_attrs(all_attrs):
    if all_attrs["stepUnits"] == 1:
        forecast_hour = pd.Timedelta(hours=all_attrs["endStep:int"])
    elif all_attrs["stepUnits"] == 0:
        forecast_hour = pd.Timedelta(minutes=all_attrs["endStep:int"])
    elif all_attrs["stepUnits"] == 2:
        forecast_hour = pd.Timedelta(days=all_attrs["endStep:int"])
    else:
        raise ValueError(f"stepUnits is not supported: {all_attrs['stepUnits']}")
    return "step", forecast_hour


def get_valid_time_from_attrs(all_attrs):
    if all_attrs["validityDate"] in ("undef", "unknown"):
        return None, None
    if all_attrs["validityTime"] in ("undef", "unknown"):
        return None, None
    valid_time = pd.to_datetime(f"{all_attrs['validityDate']}{all_attrs['validityTime']:04}")
    return "valid_time", valid_time


def get_level_from_attrs(
        all_attrs: Dict,
        level_dim_name: Optional[str] = None,
) -> Tuple[str, Union[float, int]]:
    """
    Get level coordinate name and value.

    If message has typeOfLevel, use typeOfLevel as coordinate name,
    else use "level_{typeOfFirstFixedSurface}",
    or "level_{typeOfFirstFixedSurface}_{typeOfSecondFixedSurface}" if typeOfSecondFixedSurface is not 255.

    Parameters
    ----------
    all_attrs
    level_dim_name

    Returns
    -------
    typing.Tuple[str, float or int]

    """
    if level_dim_name == "isobaricInPa":
        value = math.pow(10, all_attrs["scaleFactorOfFirstFixedSurface"]) * all_attrs["scaledValueOfFirstFixedSurface"]
        return level_dim_name, value
    elif level_dim_name in ("isobaricInhPa", "pl"):
        value = math.pow(10, all_attrs["scaleFactorOfFirstFixedSurface"]) * all_attrs["scaledValueOfFirstFixedSurface"]
        return level_dim_name, value / 100.0
    elif isinstance(level_dim_name, str):
        # TODO: add check for level_type="pl"
        return level_dim_name, all_attrs["level"]
    elif level_dim_name is None:
        if all_attrs["typeOfLevel"] not in ("undef", "unknown"):
            return all_attrs["typeOfLevel"], all_attrs["level"]
        else:
            level_name = f"level_{all_attrs['typeOfFirstFixedSurface']}"
            if all_attrs['typeOfSecondFixedSurface'] != 255:
                level_name += f"{all_attrs['typeOfSecondFixedSurface']}"
            return level_name, all_attrs["level"]
    else:
        raise TypeError(f"level_dim_name is not supported: {level_dim_name}")
