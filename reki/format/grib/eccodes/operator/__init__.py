"""Compatibility layer: the implementation has moved to ``reki.readers.grib.eccodes.operator``."""

from reki.readers.grib.eccodes.operator import (
    extract_region,
    interpolate_grid,
)

__all__ = [
    "extract_region",
    "interpolate_grid",
]
