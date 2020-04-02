from pathlib import Path
import typing

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
) -> bytes or None:
    """
    Load one message from grib file and return message's original bytes.

    Parameters
    ----------
    file_path
    parameter
    level_type
    level

    Returns
    -------
    bytes or None

    Examples
    --------
    Load bytes of 850hPa temperature from GRAPES GFS GMF and create GRIB message using `eccodes.codes_new_from_message`.

    >>> file_path = "/sstorage1/COMMONDATA/OPER/NWPC/GRAPES_GFS_GMF/Prod-grib/2020031721/ORIG/gmf.gra.2020031800105.grb2"
    >>> message_bytes = load_bytes_from_file(
    ...     file_path=file_path,
    ...     parameter="t",
    ...     level_type="pl",
    ...     level=850,
    ... )
    >>> message = eccodes.codes_new_from_message(message_bytes)
    >>> values = eccodes.codes_get_double_array(message, "values")
    >>> print(len(values))
    1036800

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
            return eccodes.codes_get_message(message_id)
