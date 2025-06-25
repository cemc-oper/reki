from typing import Union, Dict

import pandas as pd

from reki.format.grib.config import WGRIB2_SHORT_NAME_TABLE, CEMC_PARAM_TABLE


def convert_parameter(parameter: Union[str, Dict]) -> Union[str, Dict]:
    """
    Convert string parameter into GRIB keys according to short name tables.
    If parmeter is found in tables, it will be replaced by GRIB key dict.
    Or if parameter is not found, return the string.

    Currentlly reki has two short name tables (and search by order):

    * WGRIB short name table
    * CEMC param table

    Parameters
    ----------
    parameter

    Returns
    -------
    Union[str, Dict]

    Examples
    --------
    >>> from reki.format.grib.common._parameter import convert_parameter

    Convert wgrib2 short names:

    >>> convert_parameter("TMP")
    {'discipline': 0, 'parameterCategory': 0, 'parameterNumber': 0}
    >>> convert_parameter("VIS")
    {'discipline': 0, 'parameterCategory': 19, 'parameterNumber': 0}

    Convert CEMC params:

    >>> convert_parameter("bli")
    {'discipline': 0.0, 'parameterCategory': 7.0, 'parameterNumber': 1.0}
    >>> convert_parameter("t2m")
    {'discipline': 0.0, 'parameterCategory': 0.0, 'parameterNumber': 0.0}

    Unknown parameter:

    >>> convert_parameter("unknown")
    'unknown'

    dict parameter:

    >>> convert_parameter({"parameterCategory": 0, "parameterNumber": 0})
    {'parameterCategory': 0, 'parameterNumber': 0}

    """
    if isinstance(parameter, str):
        df = WGRIB2_SHORT_NAME_TABLE[WGRIB2_SHORT_NAME_TABLE["short_name"] == parameter]
        if not df.empty:
            return df.iloc[0].drop("short_name").to_dict()

        param_df = CEMC_PARAM_TABLE[CEMC_PARAM_TABLE["name"] == parameter]
        if not param_df.empty:
            row = param_df.iloc[0]
            param_key = dict(
                discipline=float(row["discipline"]),
                parameterCategory=float(row["category"]),
                parameterNumber=float(row["number"]),
            )

            if not pd.isna(row["typeOfLevel"]):
                param_key["typeOfLevel"] = row["typeOfLevel"]
            if not pd.isna(row["level"]):
                param_key["level"] = row["level"]
            if not pd.isna(row["first_level"]):
                param_key["first_level"] = float(row["first_level"])
            if not pd.isna(row["second_level"]):
                param_key["second_level"] = float(row["second_level"])
            if not pd.isna(row["stepType"]):
                param_key["stepType"] = row["stepType"]

            return param_key

    return parameter
