"""Compatibility layer: the implementation has moved to ``reki.readers.grib.config``."""

from reki.readers.grib.config import (
    WGRIB2_SHORT_NAME_TABLE,
    CEMC_PARAM_TABLE,
    GribParameterKey,
    check_value,
    find_short_name,
    find_wgrib2_name,
    find_cemc_name,
)

__all__ = [
    "WGRIB2_SHORT_NAME_TABLE",
    "CEMC_PARAM_TABLE",
    "GribParameterKey",
    "check_value",
    "find_short_name",
    "find_wgrib2_name",
    "find_cemc_name",
]
