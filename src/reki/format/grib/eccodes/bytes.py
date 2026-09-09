"""Compatibility layer: the implementation has moved to ``reki.readers.grib.eccodes.bytes``."""

from reki.readers.grib.eccodes.bytes import (
    load_bytes_from_file,
    create_message_from_bytes,
    create_messages_from_bytes,
)

__all__ = [
    "load_bytes_from_file",
    "create_message_from_bytes",
    "create_messages_from_bytes",
]
