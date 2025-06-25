from pathlib import Path
from typing import List, Dict, Union, Optional

import eccodes

from reki.format.grib.common._level import fix_level_type
from reki.format.grib.common._parameter import convert_parameter
from ._check import _check_message


def load_bytes_from_file(
        file_path: Union[str, Path],
        parameter: Union[str, Dict],
        level_type: str = None,
        level: int = None,
) -> Optional[bytes]:
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

    parameter = convert_parameter(parameter)

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


def create_message_from_bytes(raw_message: bytes) -> Optional[int]:
    """
    Create **the first** message from raw bytes.

    The returned message should be released using ``eccodes.codes_release`` manually.

    Parameters
    ----------
    raw_message

    Returns
    -------
    int or None
    """
    return eccodes.codes_new_from_message(raw_message)


def create_messages_from_bytes(raw_message: bytes) -> List[int]:
    """
    Create all messages from raw bytes.

    The returned messages should be released using ``eccodes.codes_release`` manually.

    Parameters
    ----------
    raw_message

    Returns
    -------
    int or None

    Examples
    --------
    Load raw bytes of temperature at 500hPa and 850hPa and reload them from raw bytes.
    Print level value of all returned messages.

    >>> file_path = "/sstorage1/COMMONDATA/OPER/NWPC/GRAPES_GFS_GMF/Prod-grib/2020031721/ORIG/gmf.gra.2020031800105.grb2"
    >>> message_bytes_t850 = load_bytes_from_file(
    ...     file_path=file_path,
    ...     parameter="t",
    ...     level_type="pl",
    ...     level=850,
    ... )
    >>> message_bytes_t500 = load_bytes_from_file(
    ...     file_path=file_path,
    ...     parameter="t",
    ...     level_type="pl",
    ...     level=500,
    ... )
    >>> message_bytes = message_bytes_t500 + message_bytes_t850
    >>> messages = create_messages_from_bytes(message_bytes)
    >>> for message in messages:
    ...     print(eccodes.codes_get(message, "level"))
    500
    850

    """
    messages = []
    message_bytes = raw_message

    while len(message_bytes) > 0:
        message = create_message_from_bytes(message_bytes)
        if message is None:
            break
        message_size = eccodes.codes_get_message_size(message)
        messages.append(message)
        message_bytes = message_bytes[message_size:]
    return messages
