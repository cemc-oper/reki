"""Compatibility layer: the implementation has moved to ``reki.readers.grib.eccodes``."""

from reki.readers.grib.eccodes import (
    load_message_from_file,
    load_messages_from_file,
    load_field_from_file,
    load_field_from_files,
    load_bytes_from_file,
    create_message_from_bytes,
    create_messages_from_bytes,
    create_data_array_from_message,
)

__all__ = [
    "load_message_from_file",
    "load_messages_from_file",
    "load_field_from_file",
    "load_field_from_files",
    "load_bytes_from_file",
    "create_message_from_bytes",
    "create_messages_from_bytes",
    "create_data_array_from_message",
]
