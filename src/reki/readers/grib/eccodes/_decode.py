"""Known-offset GRIB message and values decoding helpers."""

from pathlib import Path
from typing import Optional

import eccodes
import numpy as np

from reki.diagnostics import record_io_event
from ._scan import open_grib_file


def load_message_at_offset(path: str | Path, offset: int, *, headers_only=False):
    with open_grib_file(path) as file_handle:
        file_handle.seek(offset)
        message = eccodes.codes_grib_new_from_file(file_handle, headers_only=headers_only)
    return message


def decode_message_values(path: str | Path, offset: int, shape, missing_value,
                          fill_value: Optional[float] = np.nan):
    """Decode exactly one message's values at a recorded byte offset."""
    message = load_message_at_offset(path, offset)
    if message is None:
        raise ValueError(f"no GRIB message found in {path} at offset {offset}")
    try:
        eccodes.codes_set(message, "missingValue", missing_value)
        record_io_event("value_decode_count")
        values = eccodes.codes_get_double_array(message, "values")
    finally:
        eccodes.codes_release(message)
    values = values.reshape(shape)
    if fill_value is not None:
        np.place(values, values == missing_value, fill_value)
    return values
