import typing
import math

import eccodes


def _check_message(
        message_id,
        parameter: str or typing.Dict or None,
        level_type: str or typing.List[str] or None,
        level: int or typing.List[int] or typing.Dict or None,
        **kwargs,
) -> bool:
    if not _check_parameter(message_id, parameter):
        return False
    if not _check_level_type(message_id, level_type):
        return False
    if not _check_level_value(message_id, level, level_type):
        return False
    if not _check_keys(message_id, **kwargs):
        return False
    return True


def _check_parameter(message_id, parameter: str or typing.Dict or None) -> bool:
    if parameter is None:
        return True
    if isinstance(parameter, str):
        short_name = eccodes.codes_get(message_id, "shortName")
        return short_name == parameter
    elif isinstance(parameter, typing.Dict):
        for key, value in parameter.items():
            if eccodes.codes_get(message_id, key) != value:
                return False
        return True
    else:
        raise ValueError(f"parameter is not supported: {parameter}")


def _check_level_type(
        message_id,
        level_type: str or typing.List or typing.Dict or None,
) -> bool:
    if level_type is None:
        return True
    message_type = eccodes.codes_get(message_id, "typeOfLevel", ktype=str)
    if isinstance(level_type, str):
        return message_type == level_type
    elif isinstance(level_type, typing.List):
        for cur_level_type in level_type:
            if _check_level_type(message_id, cur_level_type):
                return True
        return False
    elif isinstance(level_type, typing.Dict):
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
        level: int or float or typing.List[int] or typing.Dict or None,
        level_type: str or typing.Dict or None = None
) -> bool:
    if level is None:
        return True

    message_level = eccodes.codes_get(message_id, "level", ktype=float)

    # check for `pl` using unit hPa.
    # WARNING: This may be changed.
    if isinstance(level_type, typing.Dict):
        if "typeOfFirstFixedSurface" in level_type and level_type["typeOfFirstFixedSurface"] == 100:
            level_in_pa = _get_level_value("First")
            message_level = level_in_pa / 100.0

    if isinstance(level, int) or isinstance(level, float):
        return message_level == level
    elif isinstance(level, typing.List):
        return message_level in level
    elif isinstance(level, typing.Dict):
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
    else:
        raise ValueError(f"level is not supported: {level}")


def _check_keys(message_id, **kwargs):
    for key, value in kwargs.items():
        v = eccodes.codes_get(message_id, key)
        if value != v:
            return False
    return True


def _get_level_value(message_id, name="First"):
    f = eccodes.codes_get(message_id, f"scaleFactorOf{name}FixedSurface")
    v = eccodes.codes_get(message_id, f"scaledValueOf{name}FixedSurface")
    level = math.pow(10, -1 * f) * v
    return level
