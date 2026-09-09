"""Compatibility layer: the implementation has moved to ``reki.readers.table``."""

from reki.readers.table import (
    load_table_from_file,
    load_nwpc_obs_from_file,
    NWPC_OBS_CONFIG,
)

__all__ = [
    "load_table_from_file",
    "load_nwpc_obs_from_file",
    "NWPC_OBS_CONFIG",
]
