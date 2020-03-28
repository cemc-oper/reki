from pathlib import Path
import typing
import io

import eccodes

from nwpc_data.grib.eccodes._util import (
    _check_parameter,
    _check_level_type,
    _check_level_value,
)


def load_bytes_from_file(
        file_path: str or Path,
        parameter: str or typing.Dict,
        level_type: str,
        level: int,
        **kwargs,
) -> int or None:
    offset = 0
    with open(file_path, "rb") as f:
        while True:
            message_id = eccodes.codes_grib_new_from_file(f)
            length = eccodes.codes_get(message_id, "totalLength")
            if message_id is None:
                return None
            if not _check_parameter(message_id, parameter):
                eccodes.codes_release(message_id)
                offset += length
                continue
            if not _check_level_type(message_id, level_type):
                eccodes.codes_release(message_id)
                offset += length
                continue
            if not _check_level_value(message_id, level):
                eccodes.codes_release(message_id)
                offset += length
                continue
            break

    with open(file_path, "rb") as f:
        f.seek(offset)
        b = f.read(length)
        message_bytes = io.BytesIO(b)
        return message_bytes
