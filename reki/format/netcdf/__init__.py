from pathlib import Path
from typing import Union, Dict, Optional

import xarray as xr

from reki._util import _load_first_variable


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
    file_path
    parameter
    level_type
        level type, default is level.
    level
    **kwargs
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
