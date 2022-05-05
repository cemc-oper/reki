from typing import Union, Dict, List, Optional
import math

import eccodes


def _check_message(
        message_id,
        parameter: Optional[Union[str, Dict]],
        level_type: Optional[Union[str, List[str]]],
        level: Optional[Union[int, List[int], Dict]],
        **kwargs,
) -> bool:
    """
    Check whether GRIB message (`message_id`) fits conditions.

    Currently, conditions are:
        - parameter
        - level_Type
        - level
        - other GRIB keys

    Parameters
    ----------
    message_id
    parameter
    level_type
    level
    kwargs

    Returns
    -------

    """
    if not _check_parameter(message_id, parameter):
        return False
    if not _check_level_type(message_id, level_type):
        return False
    if not _check_level_value(message_id, level, level_type):
        return False
    if not _check_keys(message_id, **kwargs):
        return False
    return True


def _check_parameter(message_id, parameter: Optional[Union[str, Dict]]) -> bool:
    if parameter is None:
        return True
    # parameter = _convert_parameter(parameter)
    if isinstance(parameter, str):
        short_name = eccodes.codes_get(message_id, "shortName")
        return short_name == parameter
    elif isinstance(parameter, Dict):
        for key, value in parameter.items():
            if eccodes.codes_get(message_id, key) != value:
                return False
        return True
    else:
        raise ValueError(f"parameter is not supported: {parameter}")


def _check_level_type(
        message_id,
        level_type: Optional[Union[str, List, Dict]],
) -> bool:
    if level_type is None:
        return True
    message_type = eccodes.codes_get(message_id, "typeOfLevel", ktype=str)
    if isinstance(level_type, str):
        return message_type == level_type
    elif isinstance(level_type, List):
        for cur_level_type in level_type:
            if _check_level_type(message_id, cur_level_type):
                return True
        return False
    elif isinstance(level_type, Dict):
        for key in level_type:
            requested_value = level_type[key]
            value = eccodes.codes_get(message_id, key, ktype=type(requested_value))
            if requested_value != value:
                return False
        return True
    else:
        raise ValueError(f"level_type is not supported: {level_type}")


def _check_level_value(
        message_id,
        level: Optional[Union[int, float, List[int], Dict]],
        level_type: Union[str, Dict] = None
) -> bool:
    if level is None:
        return True

    message_level = eccodes.codes_get(message_id, "level", ktype=float)

    # check for `pl` using unit hPa.
    # WARNING: This may be changed.
    if isinstance(level_type, Dict):
        if "typeOfFirstFixedSurface" in level_type and level_type["typeOfFirstFixedSurface"] == 100:
            level_in_pa = _get_level_value(message_id, "First")
            message_level = level_in_pa / 100.0

    if isinstance(level, int) or isinstance(level, float):
        return message_level == level
    elif isinstance(level, List):
        return message_level in level
    elif isinstance(level, Dict):
        current_level_dict = level.copy()
        if "first_level" in current_level_dict:
            required_first_level = current_level_dict.pop("first_level")
            first_level = _get_level_value(message_id, "First")
            if first_level != float(required_first_level):
                return False
        if "second_level" in current_level_dict:
            required_second_level = current_level_dict.pop("second_level")
            second_level = _get_level_value(message_id, "Second")
            if second_level != float(required_second_level):
                return False
        return _check_keys(message_id, **current_level_dict)
    elif level == "all":
        return True
    else:
        raise ValueError(f"level is not supported: {level}")


def _check_keys(message_id, **kwargs):
    for key, value in kwargs.items():
        v = eccodes.codes_get(message_id, key)
        if value != v:
            return False
    return True


def _get_level_value(message_id, name: str = "First"):
    f = eccodes.codes_get(message_id, f"scaleFactorOf{name}FixedSurface")
    v = eccodes.codes_get(message_id, f"scaledValueOf{name}FixedSurface")
    level = math.pow(10, -1 * f) * v
    return level
