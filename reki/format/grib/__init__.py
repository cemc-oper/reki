"""Compatibility layer for the legacy ``reki.format.grib`` API.

The implementation has moved to ``reki.readers.grib``. The top-level
``load_field_from_file`` is now a thin wrapper over
``reki.from_source("file", ...).sel(...).first()``, preserving the
legacy signature, semantics and return type.
"""

from typing import Dict, Literal, Optional, Union
from pathlib import Path

import xarray as xr

from reki.readers.grib import (
    load_fields_from_file,
    fix_level_type,
    load_message_from_file,
    load_messages_from_file,
)


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
    import reki

    fixed_level_type = fix_level_type(level_type, engine=engine)
    query = reki.from_source("file", file_path, engine=engine)
    field = query.sel(
        parameter=parameter, level_type=fixed_level_type, level=level, **kwargs
    ).first()
    return None if field is None else field.to_xarray()


__all__ = [
    "load_field_from_file",
    "load_fields_from_file",
    "fix_level_type",
    "load_message_from_file",
    "load_messages_from_file",
]
