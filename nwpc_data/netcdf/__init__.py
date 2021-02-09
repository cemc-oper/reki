from pathlib import Path
import typing

import pandas as pd
import xarray as xr


def load_field_from_file(
        file_path: str or Path,
        parameter: str or typing.Dict = None,
        level_type: str or typing.Dict = None,
        level: int = None,
        **kwargs
) -> xr.DataArray or None:
    """
    Load **one** field from NetCDF file.

    Parameters
    ----------
    file_path: str
    parameter: str or typing.Dict
    level_type: str or typing.Dict
        level type, pl, sfc, ml, or use ecCodes key `typeOfLevel`, or set ecCodes keys directly.
    level: int or None
    kwargs: dict
        other parameters used by engine.

    Returns
    -------
    DataArray or None:
        DataArray if found one field, or None if not.
    """
    with xr.open_dataset(file_path) as ds:
        if parameter is None:
            return _load_first_variable(ds)
        else:
            return ds[parameter]


def _load_first_variable(data_set: xr.Dataset) -> xr.DataArray:
    first_variable_name = list(data_set.data_vars)[0]
    return data_set[first_variable_name]
