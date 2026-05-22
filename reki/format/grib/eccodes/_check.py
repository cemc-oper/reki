from typing import Union, Optional, Literal, Type
import math

import eccodes


def _check_message(
        message_id,
        parameter: Optional[Union[str, dict]],
        level_type: Optional[Union[str, list[str]]],
        level: Optional[Union[int, list[int], dict]],
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
    bool
    """
    conditions = dict()

    parameter_conditions = get_parameter_conditions(parameter)
    conditions.update(parameter_conditions)

    level_type_conditions = get_level_type_conditions(level_type)
    conditions.update(level_type_conditions)

    level_value_conditions = get_level_value_conditions(level, level_type)
    conditions.update(level_value_conditions)

    additional_conditions = {}
    for key, expected_value in kwargs.items():
        if ":" not in key:
            key = combine_key_name_with_type(key, expected_value)
        additional_conditions[key] = expected_value

    conditions.update(additional_conditions)

    return check_conditions(message_id, conditions)


def get_parameter_conditions(
        parameter: Optional[Union[str, dict]]
) -> dict[str, Union[int, float, str]]:
    if parameter is None:
        return dict()
    # parameter = _convert_parameter(parameter)
    if isinstance(parameter, str):
        return {
            "shortName": parameter
        }
    elif isinstance(parameter, dict):
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
        level: Optional[Union[int, float, list[int], dict]],
        level_type: Union[str, dict] = None
) -> dict[str, Union[int, float, str, list]]:
    if level is None:
        return dict()

    if isinstance(level, int) or isinstance(level, float):
        return {
            "level": level
        }
    elif isinstance(level, list):
        return {
            "level": level
        }
    elif isinstance(level, dict):
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
        message_level = get_grib_key_value(message_id, "level", ktype=float)
        # check for `pl` using unit hPa.
        # WARNING: This may be changed.
        if "typeOfFirstFixedSurface:int" in conditions and conditions["typeOfFirstFixedSurface:int"] == 100:
            level_in_pa = get_level_value(message_id, "First")
            message_level = level_in_pa / 100.0

        expected_value = current_condition_dict.pop("level")

        if not check_value(expected_value, message_level):
            return False

    for key, expected_value in current_condition_dict.items():
        try:
            v = get_grib_key_value(message_id, key)
        except eccodes.KeyValueNotFoundError:
            return False
        if not check_value(expected_value, v):
            return False
    return True


def combine_key_name_with_type(key: str, value: Union[str, int, float, list]) -> str:
    """
    combine key name with type according to value.

    Parameters
    ----------
    key: str
        key name
    value: Union[str, int, float, list]
        value

    Returns
    -------
    str
        key name with type
    """
    if isinstance(value, str):
        return key + ":str"
    elif isinstance(value, int):
        return key + ":int"
    elif isinstance(value, float):
        return key + ":float"
    elif isinstance(value, list):
        return combine_key_name_with_type(key, value[0])
    else:
        raise ValueError(f"value is not supported: {value}")


def get_level_value(message_id, name: Literal['First', 'Second'] = "First"):
    f = get_grib_key_value(message_id, f"scaleFactorOf{name}FixedSurface:float")
    v = get_grib_key_value(message_id, f"scaledValueOf{name}FixedSurface:float")
    level = math.pow(10, -1 * f) * v
    return level


def get_grib_key_value(
        message_id,
        key: str,
        ktype: Optional[Type[int], Type[float], Type[str]] = None,
) -> Union[str, int, float]:
    """
    Get value of GRIB key.

    Parameters
    ----------
    message_id
    key
        key name, or key name and type, e.g. "level", "level:float"
    ktype
        key type, if set, type in key is ignored.

    Returns
    -------
    Union[str, int, float]
        value of GRIB key
    """
    if ":" in key and ktype is None:
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
