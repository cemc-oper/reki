"""Known-offset GRIB message and values decoding helpers."""

from pathlib import Path
from typing import Optional

import eccodes
import numpy as np

from reki.grib_io import decode_values, load_message_at_offset


def decode_message_values(
    path: str | Path,
    offset: int,
    shape,
    missing_value,
    fill_value: Optional[float] = np.nan,
):
    """Decode exactly one message's values at a recorded byte offset."""
    message = load_message_at_offset(path, offset)
    if message is None:
        raise ValueError(f"no GRIB message found in {path} at offset {offset}")
    try:
        return decode_values(message, missing_value=missing_value, fill_value=fill_value).reshape(shape)
    finally:
        eccodes.codes_release(message)
