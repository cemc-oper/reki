import typing
import math

import eccodes
import numpy as np
import xarray as xr
import pandas as pd


def create_data_array_from_message(
        message,
        level_dim_name: str or None = None,
) -> xr.DataArray:
    """
    Create ``xarray.DataArray`` from one GRIB 2 message.
    """
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
        'endStep',
        "name",
        "shortName",
        'cfName',
        'discipline',
        'parameterCategory',
        'parameterNumber',
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

    level_keys = [
        "typeOfFirstFixedSurface",
        "typeOfSecondFixedSurface",
        "scaleFactorOfFirstFixedSurface",
        "scaledValueOfFirstFixedSurface",
    ]

    all_keys = attr_keys + grid_keys + level_keys

    all_attrs = {}
    for key in all_keys:
        try:
            value = eccodes.codes_get(message, key)
        except:
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

    coords = {}

    # add time and step coordinate
    time_name, value = get_time_from_attrs(all_attrs)
    coords[time_name] = value

    step_name, value = get_step_from_attrs(all_attrs)
    coords[step_name] = value

    # add level coordinate
    level_name, value = get_level_from_attrs(all_attrs, level_dim_name)
    coords[level_name] = value

    coords["latitude"] = lats
    coords["longitude"] = lons

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
    if "shortName" in all_attrs:
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


def get_level_coordinate_name(data: xr.DataArray) -> str or None:
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
    start_time = pd.to_datetime(f"{all_attrs['dataDate']}{all_attrs['dataTime']:04}")
    return "time", start_time


def get_step_from_attrs(all_attrs):
    if all_attrs["stepUnits"] == 1:
        forecast_hour = pd.Timedelta(hours=all_attrs["endStep"])
    elif all_attrs["stepUnits"] == 0:
        forecast_hour = pd.Timedelta(minutes=all_attrs["endStep"])
    elif all_attrs["stepUnits"] == 2:
        forecast_hour = pd.Timedelta(days=all_attrs["endStep"])
    else:
        raise ValueError(f"stepUnits is not supported: {all_attrs['stepUnits']}")
    return "step", forecast_hour


def get_level_from_attrs(
        all_attrs: dict,
        level_dim_name: str or None = None,
) -> typing.Tuple[str, float or int]:
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
