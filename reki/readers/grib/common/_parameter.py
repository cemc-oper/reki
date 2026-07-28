from typing import Union, Dict

from reki.readers.grib.config import find_parameter_record


def convert_parameter(parameter: Union[str, Dict]) -> Union[str, Dict]:
    """
    Convert string parameter into GRIB keys according to the parameter registry.
    If parameter is found in the registry, it will be replaced by a GRIB key dict.
    Or if parameter is not found, return the string.

    The registry is searched in the following order:

    * WGRIB2 short names (``wgrib2_name``)
    * CEMC variant names and aliases
    * CEMC generic names (entry ``name``)

    Parameters
    ----------
    parameter

    Returns
    -------
    Union[str, Dict]

    Examples
    --------
    >>> from reki.readers.grib.common._parameter import convert_parameter

    Convert wgrib2 short names:

    >>> convert_parameter("TMP")
    {'discipline': 0, 'parameterCategory': 0, 'parameterNumber': 0}
    >>> convert_parameter("VIS")
    {'discipline': 0, 'parameterCategory': 19, 'parameterNumber': 0}

    Convert CEMC params:

    >>> convert_parameter("bli")
    {'discipline': 0.0, 'parameterCategory': 7.0, 'parameterNumber': 1.0, 'typeOfLevel': 'surface'}
    >>> convert_parameter("t2m")
    {'discipline': 0.0, 'parameterCategory': 0.0, 'parameterNumber': 0.0, 'typeOfLevel': 'heightAboveGround', 'level': 2, 'first_level': 2.0}

    Unknown parameter:

    >>> convert_parameter("unknown")
    'unknown'

    dict parameter:

    >>> convert_parameter({"parameterCategory": 0, "parameterNumber": 0})
    {'parameterCategory': 0, 'parameterNumber': 0}

    """
    if not isinstance(parameter, str):
        return parameter

    found = find_parameter_record(parameter)
    if found is None:
        return parameter

    discipline, category, number = found["key"]
    if found["source"] == "wgrib2":
        return {
            "discipline": discipline,
            "parameterCategory": category,
            "parameterNumber": number,
        }

    record = found["record"]
    param_key = {
        "discipline": float(discipline),
        "parameterCategory": float(category),
        "parameterNumber": float(number),
    }

    # informational legacy fields, used as ecCodes/cfgrib filter keys
    if record.get("typeOfLevel") is not None:
        param_key["typeOfLevel"] = record["typeOfLevel"]
    if record.get("level") is not None:
        param_key["level"] = record["level"]

    when = record.get("when", {})
    if when.get("first_level") is not None:
        param_key["first_level"] = float(when["first_level"])
    if when.get("second_level") is not None:
        param_key["second_level"] = float(when["second_level"])
    if when.get("stepType") is not None:
        param_key["stepType"] = when["stepType"]

    return param_key
