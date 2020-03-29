import typing
from pathlib import Path

import xarray as xr

from .cfgrib import load_fields_from_file


def load_field_from_file(
        file_path: str or Path,
        parameter: str or typing.Dict,
        level_type: str,
        level: int or None = None,
        engine: str = "cfgrib",
        **kwargs
) -> xr.DataArray or None:
    """
    Load **one** field from GRIB2 file. Default engine is cfgrib.

    If loading speed is

    Parameters
    ----------
    file_path: str
    parameter: str or typing.Dict
    level_type: str
    level: int or None
    engine: str
        cfgrib or eccodes
    kwargs: dict
        other parameters used by engine.

    Returns
    -------
    DataArray or None:
        DataArray if found one field, or None if not.
    """
    if engine == "cfgrib":
        from .cfgrib import load_field_from_file
        return load_field_from_file(
            file_path,
            parameter,
            level_type,
            level,
            **kwargs,
        )
    elif engine == "eccodes":
        from .eccodes import load_field_from_file
        return load_field_from_file(
            file_path,
            parameter,
            level_type,
            level,
        )
    else:
        raise ValueError(f"engine {engine} is not supported")
