import typing
from pathlib import Path

import eccodes
# from tqdm import tqdm

from nwpc_data.grib.eccodes._level import _fix_level
from ._util import (
    _check_parameter,
    _check_level_type,
    _check_level_value,
    _check_keys,
    _check_message,
)


def load_message_from_file(
        file_path: str or Path,
        parameter: str or typing.Dict or None = None,
        level_type: str or typing.Dict or None = None,
        level: int or float or None = None,
        **kwargs,
) -> int or None:
    """
    Load the **first** message from GRIB 2 file using eccodes-python library.

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

    level_type: str or typing.Dict
        level type.
    level: int or float
        level value.
    kwargs: dict
        other grib key used to filter.

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
    fixed_level_type, _ = _fix_level(level_type, None)
    with open(file_path, "rb") as f:
        while True:
            message_id = eccodes.codes_grib_new_from_file(f)
            if message_id is None:
                return None
            if not _check_message(message_id, parameter, fixed_level_type, level, **kwargs):
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
        level_type: str or typing.Dict or typing.List or None = None,
        level: int or float or typing.List or None = None,
        **kwargs,
) -> typing.List or None:
    """
    Load multiply messages from file.

    This function will scan all messages in GRIB 2 file and return all messages which fit conditions.

    Parameters
    ----------
    file_path: str or Path
    parameter: str or typing.Dict
        see ``load_message_from_file``, required option.
    level_type: str or typing.List or None
        level type.
        - string, same as ``load_message_from_file``
        - typing.List, level type should be in the list.
        - None, don't check level type.
    level: int or float or typing.Dict or typing.List or None
        level value.
        - string, same as ``load_message_from_file``
        - typing.Dict, same as ``load_message_from_file``
        - typing.List, level value should be in the list.
        - None, don't check level value. For example, load all messages of some typeOfLevel.
    kwargs: dict
        other grib key used to filter.

    Returns
    -------
    typing.List or None:
        a list of message number or None if no message is found.
    """
    fixed_level_type, _ = _fix_level(level_type, None)

    messages = []

    # print("count...")
    # with open(file_path, "rb") as f:
    #     total_count = eccodes.codes_count_in_file(f)
    #     print(total_count)
    # print("count..done")

    with open(file_path, "rb") as f:
        # pbar = tqdm(total=total_count)
        while True:
            message_id = eccodes.codes_grib_new_from_file(f)
            if message_id is None:
                break
            # pbar.update(1)
            if not _check_parameter(message_id, parameter):
                eccodes.codes_release(message_id)
                continue
            if not _check_level_type(message_id, fixed_level_type):
                eccodes.codes_release(message_id)
                continue
            if not _check_level_value(message_id, level):
                eccodes.codes_release(message_id)
                continue
            if not _check_keys(message_id, **kwargs):
                eccodes.codes_release(message_id)
                continue

            # clone message
            new_message_id = eccodes.codes_clone(message_id)
            eccodes.codes_release(message_id)
            messages.append(new_message_id)
        # pbar.close()
        if len(messages) == 0:
            return None
        return messages
