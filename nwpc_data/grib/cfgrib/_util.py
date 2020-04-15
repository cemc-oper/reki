import typing

import xarray as xr


def _fill_parameter(
        parameter: str or dict,
        filter_by_keys: dict,
        read_keys: typing.List
) -> typing.Tuple[typing.Dict, typing.List]:
    if isinstance(parameter, str):
        filter_by_keys["shortName"] = parameter
    elif isinstance(parameter, typing.Dict):
        filter_by_keys.update(parameter)
        read_keys.extend(parameter.keys())
    else:
        raise ValueError(f"parameter is not supported: {parameter}")
    return filter_by_keys, read_keys


def _fill_level(
        level_type: str,
        level: int,
        filter_by_keys: typing.Dict,
        read_keys: typing.List
) -> typing.Tuple[typing.Dict, typing.List]:
    filter_by_keys.update({
        "typeOfLevel": level_type,
        "level": level,
    })
    return filter_by_keys, read_keys


def _fill_level_type(
        level_type: str or dict,
        filter_by_keys: typing.Dict,
        read_keys: typing.List
) -> typing.Tuple[typing.Dict, typing.List]:
    if isinstance(level_type, dict):
        filter_by_keys.update(level_type)
        read_keys.extend([key for key in level_type if key not in read_keys])
    else:
        filter_by_keys.update({
            "typeOfLevel": level_type,
        })
    return filter_by_keys, read_keys


def _fill_level_value(
        level: int or float,
        filter_by_keys: typing.Dict,
        read_keys: typing.List
) -> typing.Tuple[typing.Dict, typing.List]:
    filter_by_keys.update({
        "level": level,
    })
    return filter_by_keys, read_keys


def _fill_index_path(
        with_index: str or bool,
        backend_kwargs: typing.Dict,
) -> typing.Dict:
    if isinstance(with_index, str):
        backend_kwargs["indexpath"] = with_index
    elif isinstance(with_index, bool):
        if not with_index:
            backend_kwargs["indexpath"] = ""
    return backend_kwargs


def _load_first_variable(data_set: xr.Dataset) -> xr.DataArray:
    first_variable_name = list(data_set.data_vars)[0]
    return data_set[first_variable_name]