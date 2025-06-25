from typing import Optional, Union, List, Dict

from ._check import _check_message
from ._level import _fix_level
from reki.format.grib.common import convert_parameter


def check_message_with_level_fix(
        message_id,
        parameter: Optional[Union[str, Dict]],
        level_type: Optional[Union[str, List[str]]],
        level: Optional[Union[int, List[int], Dict]],
        **kwargs,
) -> bool:
    """
    Check whether GRIB message fits conditions.

    Parameters
    ----------
    message_id
    parameter
    level_type
    level
    kwargs

    Returns
    -------
    bool
    """
    # parameter = _convert_parameter(parameter)
    level_type, _ = _fix_level(level_type, None)

    return _check_message(
        message_id,
        parameter=parameter,
        level_type=level_type,
        level=level,
        **kwargs
    )
