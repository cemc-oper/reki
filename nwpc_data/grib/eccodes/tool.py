from pathlib import Path
import typing
import io

import eccodes

from nwpc_data.grib.eccodes._util import (
    _check_message,
)
from nwpc_data.grib._level import fix_level_type


def load_bytes_from_file(
        file_path: str or Path,
        parameter: str or typing.Dict,
        level_type: str = None,
        level: int = None,
) -> io.BytesIO or None:
    """
    Load one message from grib file and return a file-like io.BytesIO object.

    Parameters
    ----------
    file_path
    parameter
    level_type
    level

    Returns
    -------
    io.BytesIO or None
    """
    offset = 0
    fixed_level_type = fix_level_type(level_type)
    with open(file_path, "rb") as f:
        while True:
            message_id = eccodes.codes_grib_new_from_file(f)
            length = eccodes.codes_get(message_id, "totalLength")
            if message_id is None:
                return None
            if not _check_message(message_id, parameter, fixed_level_type, level):
                eccodes.codes_release(message_id)
                offset += length
                continue
            break

    with open(file_path, "rb") as f:
        f.seek(offset)
        b = f.read(length)
        message_bytes = io.BytesIO(b)
        return message_bytes
