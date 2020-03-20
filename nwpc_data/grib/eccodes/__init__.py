from pathlib import Path
import typing

import eccodes

from nwpc_data.grib.eccodes._util import (
    _check_parameter,
    _check_level_type,
    _check_level_value,
)


def load_field_from_file(
        file_path: str or Path,
        parameter: str or typing.Dict,
        level_type: str,
        level: int,
        **kwargs,
) -> int or None:
    with open(file_path, "rb") as f:
        while True:
            message_id = eccodes.codes_grib_new_from_file(f)
            if message_id is None:
                return None
            if not _check_parameter(message_id, parameter):
                eccodes.codes_release(message_id)
                continue
            if not _check_level_type(message_id, level_type):
                eccodes.codes_release(message_id)
                continue
            if not _check_level_value(message_id, level):
                eccodes.codes_release(message_id)
                continue

            # clone message
            new_message_id = eccodes.codes_clone(message_id)
            eccodes.codes_release(message_id)
            return new_message_id
        return None


def load_fields_from_file(
        file_path: str or Path,
        parameter: str or typing.Dict,
        level_type: str or typing.List or None = None,
        level: int or typing.List or None = None,
        **kwargs,
) -> typing.List or None:
    messages = []
    with open(file_path, "rb") as f:
        while True:
            message_id = eccodes.codes_grib_new_from_file(f)
            if message_id is None:
                break
            if not _check_parameter(message_id, parameter):
                eccodes.codes_release(message_id)
                continue
            if not _check_level_type(message_id, level_type):
                eccodes.codes_release(message_id)
                continue
            if not _check_level_value(message_id, level):
                eccodes.codes_release(message_id)
                continue

            # clone message
            new_message_id = eccodes.codes_clone(message_id)
            eccodes.codes_release(message_id)
            messages.append(new_message_id)
        if len(messages) == 0:
            return None
        return messages
