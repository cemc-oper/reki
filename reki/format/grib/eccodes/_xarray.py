"""Compatibility layer: the implementation has moved to ``reki.readers.grib.eccodes._xarray``."""

from reki.readers.grib.eccodes._xarray import (
    create_data_array_from_message,
    get_attrs_from_message,
    attrs_to_grib_parameter_key,
    get_field_name,
    get_level_coordinate_name,
    get_time_from_attrs,
    get_step_from_attrs,
    get_valid_time_from_attrs,
    get_level_from_attrs,
)

__all__ = [
    "create_data_array_from_message",
    "get_attrs_from_message",
    "attrs_to_grib_parameter_key",
    "get_field_name",
    "get_level_coordinate_name",
    "get_time_from_attrs",
    "get_step_from_attrs",
    "get_valid_time_from_attrs",
    "get_level_from_attrs",
]
