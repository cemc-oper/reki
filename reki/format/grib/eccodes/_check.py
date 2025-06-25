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
    conditions = dict()

    parameter_conditions = get_parameter_conditions(parameter)
    conditions.update(parameter_conditions)

    level_type_conditions = get_level_type_conditions(level_type)
    conditions.update(level_type_conditions)

    level_value_conditions = get_level_value_conditions(level, level_type)
    conditions.update(level_value_conditions)

    conditions.update(kwargs)

    return check_conditions(message_id, conditions)


def get_parameter_conditions(parameter: Optional[Union[str, Dict]]) -> dict[str, Union[int, float, str]]:
    if parameter is None:
        return dict()
    # parameter = _convert_parameter(parameter)
    if isinstance(parameter, str):
        return {
            "shortName": parameter
        }
    elif isinstance(parameter, Dict):
        return parameter
    else:
        raise ValueError(f"parameter is not supported: {parameter}")


def get_level_type_conditions(
        level_type: Optional[Union[str, list, dict]],
) -> dict[str, Union[int, float, str, list]]:
    if level_type is None:
        return dict()
    if isinstance(level_type, str):
        return {
            "typeOfLevel": level_type
        }
    elif isinstance(level_type, list):
        return {
            "typeOfLevel": level_type
        }
    elif isinstance(level_type, dict):
        return level_type
    else:
        raise ValueError(f"level_type is not supported: {level_type}")


def get_level_value_conditions(
        level: Optional[Union[int, float, List[int], Dict]],
        level_type: Union[str, Dict] = None
) -> dict[str, Union[int, float, str, list]]:
    if level is None:
        return dict()

    if isinstance(level, int) or isinstance(level, float):
        return {
            "level": level
        }
    elif isinstance(level, List):
        return {
            "level": level
        }
    elif isinstance(level, Dict):
        return level
    elif level == "all":
        return dict()
    else:
        raise ValueError(f"level is not supported: {level}")


def check_conditions(message_id, conditions: dict):
    current_condition_dict = conditions.copy()
    if "first_level" in current_condition_dict:
        required_first_level = current_condition_dict.pop("first_level")
        first_level = get_level_value(message_id, "First")
        if first_level != float(required_first_level):
            return False
    if "second_level" in current_condition_dict:
        required_second_level = current_condition_dict.pop("second_level")
        second_level = get_level_value(message_id, "Second")
        if second_level != float(required_second_level):
            return False

    if "level" in current_condition_dict:
        message_level = get_key_value_from_message(message_id, "level", ktype=float)
        # check for `pl` using unit hPa.
        # WARNING: This may be changed.
        if "typeOfFirstFixedSurface:int" in conditions and conditions["typeOfFirstFixedSurface:int"] == 100:
            level_in_pa = get_level_value(message_id, "First")
            message_level = level_in_pa / 100.0

        expected_value = current_condition_dict.pop("level")

        if not check_value(expected_value, message_level):
            return False

    for key, expected_value in current_condition_dict.items():
        v = get_key_value_from_message(message_id, key)
        if not check_value(expected_value, v):
            return False
    return True


def get_level_value(message_id, name: str = "First"):
    f = get_key_value_from_message(message_id, f"scaleFactorOf{name}FixedSurface:float")
    v = get_key_value_from_message(message_id, f"scaledValueOf{name}FixedSurface:float")
    level = math.pow(10, -1 * f) * v
    return level


def get_key_value_from_message(message_id, key: str, ktype=None):
    if ":" in key:
        keys = key.split(":")
        key = keys[0]
        key_type = keys[1]
        if key_type == "str":
            ktype = str
        elif key_type == "int":
            ktype = int
        elif key_type == "float":
            ktype = float
        else:
            raise ValueError(f"key_type is not supported: {key_type}")
    return eccodes.codes_get(message_id, key, ktype=ktype)


def check_value(expected_value, value):
    if isinstance(expected_value, list):
        return value in expected_value
    else:
        return expected_value == value
