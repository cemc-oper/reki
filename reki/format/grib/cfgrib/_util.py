from typing import Dict, List, Union, Tuple

import numpy as np

from reki.format.grib.common import convert_parameter


def _fill_parameter(
        parameter: Union[str, Dict],
        filter_by_keys: Dict,
        read_keys: List
) -> Tuple[Dict, List]:
    parameter = convert_parameter(parameter)

    if isinstance(parameter, str):
        filter_by_keys["shortName"] = parameter
    elif isinstance(parameter, Dict):
        # TODO: convert int64 to int, move to another place.
        for key, value in parameter.items():
            if isinstance(value, np.int64):
                parameter[key] = int(value)

        filter_by_keys.update(parameter)
        read_keys.extend(parameter.keys())
    else:
        raise ValueError(f"parameter is not supported: {parameter}")
    return filter_by_keys, read_keys


def _fill_level(
        level_type: str,
        level: int,
        filter_by_keys: Dict,
        read_keys: List
) -> Tuple[Dict, List]:
    filter_by_keys.update({
        "typeOfLevel": level_type,
        "level": level,
    })
    return filter_by_keys, read_keys


def _fill_level_type(
        level_type: Union[str, dict],
        filter_by_keys: Dict,
        read_keys: List
) -> Tuple[Dict, List]:
    if isinstance(level_type, dict):
        filter_by_keys.update(level_type)
        read_keys.extend([key for key in level_type if key not in read_keys])
    else:
        filter_by_keys.update({
            "typeOfLevel": level_type,
        })
    return filter_by_keys, read_keys


def _fill_level_value(
        level: Union[int, float],
        filter_by_keys: Dict,
        read_keys: List
) -> Tuple[Dict, List]:
    filter_by_keys.update({
        "level": level,
    })
    return filter_by_keys, read_keys


def _fill_index_path(
        with_index: Union[str, bool],
        backend_kwargs: Dict,
) -> Dict:
    if isinstance(with_index, str):
        backend_kwargs["indexpath"] = with_index
    elif isinstance(with_index, bool):
        if not with_index:
            backend_kwargs["indexpath"] = ""
    return backend_kwargs
