from pathlib import Path
import typing
from typing import Union, Dict, Optional

import xarray as xr


def load_field_from_file(
        file_path: str or Path,
        parameter: Union[str, Dict] = None,
        level_type: Union[str, Dict] = None,
        level: Optional[Union[int, float]] = None,
        **kwargs
) -> Optional[xr.DataArray]:
    """
    Load **one** field from NetCDF file.

    Parameters
    ----------
    file_path: str
    parameter: str or typing.Dict
    level_type: str or typing.Dict
        level type, default is level.
    level: int or None
    kwargs: typing.Union[int, float] or None
        other parameters used by engine.

    Returns
    -------
    DataArray or None:
        DataArray if found one field, or None if not.
    """
    ds = xr.open_dataset(file_path)
    if parameter is None:
        field = _load_first_variable(ds)
    else:
        field = ds[parameter]

    if level is not None:
        if level_type is None:
            level_type = "level"
        field = field.loc[{
            level_type: level
        }]

    return field


def _load_first_variable(data_set: xr.Dataset) -> xr.DataArray:
    first_variable_name = list(data_set.data_vars)[0]
    return data_set[first_variable_name]
