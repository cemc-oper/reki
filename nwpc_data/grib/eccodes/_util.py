import typing

import eccodes


def _check_message(
        message_id,
        parameter: str or typing.Dict,
        level_type: str or typing.List[str] or None,
        level: int or typing.List[int] or None,
) -> bool:
    if not _check_parameter(message_id, parameter):
        return False
    if not _check_level_type(message_id, level_type):
        return False
    if not _check_level_value(message_id, level):
        return False
    return True


def _check_parameter(message_id, parameter: str or typing.Dict) -> bool:
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
        level_type: str or typing.List[str] or None,
) -> bool:
    if level_type is None:
        return True
    message_type = eccodes.codes_get(message_id, "typeOfLevel", ktype=str)
    if isinstance(level_type, str):
        return message_type == level_type
    elif isinstance(level_type, typing.List):
        return message_type in level_type
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
        level: int or typing.List[int] or None,
) -> bool:
    if level is None:
        return True
    message_level = eccodes.codes_get(message_id, "level", ktype=int)
    if isinstance(message_level, int):
        return message_level == level
    elif isinstance(message_level, typing.List):
        return message_level in level
    else:
        raise ValueError(f"level is not supported: {level}")
