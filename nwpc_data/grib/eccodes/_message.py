import typing
from pathlib import Path

import eccodes

from nwpc_data.grib._level import fix_level_type
from ._util import (
    _check_parameter,
    _check_level_type,
    _check_level_value,
    _check_message,
)


def load_message_from_file(
        file_path: str or Path,
        parameter: str or typing.Dict,
        level_type: str,
        level: int or float,
        **kwargs,
) -> int or None:
    """
    Load one message from GRIB 2 file using eccodes-python library.

    Returned message is a copied one of original message and file is closed before return.
    And the returned message should be released by user using `eccodes.codes_release()`.

    Parameters
    ----------
    file_path: str or Path
        GRIB 2 file path.
    parameter: str or typing.Dict
        short name of the field or a dictionary including some GRIB keys:
        - discipline
        - parameterCategory
        - parameterNumber
    level_type: str
        level type
    level: int
        level value.
    kwargs: dict
        ignored

    Returns
    -------
    int or None
        GRIB handler (int) if found or None if not found.

    Examples
    --------
    Load 850hPa temperature from GRAPES GFS and get values from GRIB message.
    >>> t = load_message_from_file(
    ...     file_path="/g1/COMMONDATA/OPER/NWPC/GRAPES_GFS_GMF/Prod-grib/2020031721/ORIG/gmf.gra.2020031800105.grb2",
    ...     parameter="t",
    ...     level_type="isobaricInhPa",
    ...     level=850,
    ... )
    >>> data = eccodes.codes_get_double_array(t, "values")
    >>> data = data.reshape([720, 1440])
    >>> data
    array([[249.19234375, 249.16234375, 249.16234375, ..., 249.15234375,
        249.19234375, 249.14234375],
       [249.45234375, 249.45234375, 249.42234375, ..., 249.45234375,
        249.44234375, 249.44234375],
       [249.69234375, 249.68234375, 249.68234375, ..., 249.70234375,
        249.67234375, 249.68234375],
       ...,
       [235.33234375, 235.45234375, 235.62234375, ..., 235.47234375,
        235.63234375, 235.48234375],
       [235.78234375, 235.91234375, 235.64234375, ..., 235.80234375,
        235.72234375, 235.82234375],
       [235.66234375, 235.86234375, 235.82234375, ..., 235.85234375,
        235.68234375, 235.70234375]])

    """
    fixed_level_type = fix_level_type(level_type)
    with open(file_path, "rb") as f:
        while True:
            message_id = eccodes.codes_grib_new_from_file(f)
            if message_id is None:
                return None
            if not _check_message(message_id, parameter, fixed_level_type, level):
                eccodes.codes_release(message_id)
                continue

            # clone message
            new_message_id = eccodes.codes_clone(message_id)
            eccodes.codes_release(message_id)
            return new_message_id
        return None


def load_messages_from_file(
        file_path: str or Path,
        parameter: str or typing.Dict,
        level_type: str or typing.List or None = None,
        level: int or float or typing.List or None = None,
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
