import typing
from typing import Union, List, Dict, Optional
from pathlib import Path

import eccodes
# from tqdm import tqdm

from ._level import _fix_level
from ._check import _check_message

from reki.format.grib.common._parameter import convert_parameter


def load_message_from_file(
        file_path: Union[str, Path],
        parameter: Union[str, Dict] = None,
        level_type: Union[str, Dict] = None,
        level: Union[int, float, Dict] = None,
        count: int = None,
        look_parameter: bool = True,
        **kwargs,
) -> Optional[int]:
    """
    Load the **first** message from GRIB 2 file using eccodes-python library.

    Returned message is a copied one of original message and file is closed before return.
    And the returned message should be released by user using `eccodes.codes_release()`.

    Parameters
    ----------
    file_path
        GRIB 2 file path.
    parameter
        short name of the field, or a dict of GRIB keys:

        * discipline
        * parameterCategory
        * parameterNumber

    level_type
        level type.
    level
        level value.
    kwargs
        other grib key used to filter.
    count
        grib message index in grib file, starting with 1.

        This option will make all others options ignored.

    Returns
    -------
    Union[int]
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
    >>> eccodes.codes_release(t)

    """
    if count is not None:
        return _load_message_from_file_by_count(file_path, count)

    fixed_level_type, _ = _fix_level(level_type, None)

    if look_parameter:
        parameter = convert_parameter(parameter)

    with open(file_path, "rb") as f:
        while True:
            message_id = eccodes.codes_grib_new_from_file(f)
            if message_id is None:
                return None
            if not _check_message(message_id, parameter, fixed_level_type, level, **kwargs):
                eccodes.codes_release(message_id)
                continue
            return message_id

            # # clone message
            # new_message_id = eccodes.codes_clone(message_id)
            # eccodes.codes_release(message_id)
            # return new_message_id
        return None


def load_messages_from_file(
        file_path: Union[str, Path],
        parameter: Union[str, Dict],
        level_type: Union[str, Dict, List] = None,
        level: Union[int, float, List, Dict] = None,
        **kwargs,
) -> Optional[List]:
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

    parameter = convert_parameter(parameter)

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
            if not _check_message(message_id, parameter, fixed_level_type, level, **kwargs):
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


def _load_message_from_file_by_count(file_path, count):
    current_index = 0
    with open(file_path, "rb") as f:
        while True:
            message_id = eccodes.codes_grib_new_from_file(f)
            if message_id is None:
                return None
            current_index += 1
            if current_index == count:
                return message_id
            else:
                eccodes.codes_release(message_id)
