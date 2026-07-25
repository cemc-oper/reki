"""Compatibility layer: the implementation has moved to ``reki.readers.grib.cfgrib``."""

from reki.readers.grib.cfgrib import (
    load_field_from_file,
    load_fields_from_file,
)

__all__ = [
    "load_field_from_file",
    "load_fields_from_file",
]
