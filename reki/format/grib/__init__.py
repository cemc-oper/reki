from typing import Union, Optional, Dict, Literal
from pathlib import Path

import xarray as xr

from .cfgrib import load_fields_from_file
from .common import fix_level_type


def load_field_from_file(
        file_path: Union[str, Path],
        parameter: Union[str, Dict],
        level_type: Optional[Union[str, Dict]] = None,
        level: Optional[int] = None,
        engine: Literal["eccodes", "cfgrib"] = "eccodes",
        **kwargs
) -> Optional[xr.DataArray]:
    """
    Load **one** field from GRIB2 file. Default engine is eccodes.

    Parameters
    ----------
    file_path
    parameter
    level_type
        level type, pl, sfc, ml, or use ecCodes key `typeOfLevel`, or set ecCodes keys directly.
    level
    engine
        GRIB decoding engine, default

        * `eccodes`: use eccodes
        * `cfgrib`: use cfgrib

    kwargs
        other parameters used by engine.

    Returns
    -------
    Optional[xr.DataArray]
        DataArray if found one field, or None if not.
    """
    fixed_level_type = fix_level_type(level_type, engine=engine)
    if engine == "cfgrib":
        from .cfgrib import load_field_from_file
        return load_field_from_file(
            file_path,
            parameter,
            fixed_level_type,
            level,
            **kwargs,
        )
    elif engine == "eccodes":
        from .eccodes import load_field_from_file
        return load_field_from_file(
            file_path,
            parameter,
            fixed_level_type,
            level,
            **kwargs
        )
    else:
        raise ValueError(f"engine {engine} is not supported")
