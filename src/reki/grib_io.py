"""Shared ecCodes I/O with no legacy-reader or cfgrib imports."""

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import eccodes
import numpy as np

from reki.diagnostics import record_io_event
from reki._legacy import reader_errors
from cedarkit_query import SourceError


@dataclass
class GribHeader:
    ordinal: int
    offset: int
    handle: int
    message_length: int | None = None

    def release(self):
        if self.handle is not None:
            eccodes.codes_release(self.handle)
            self.handle = None

    def detach(self):
        """Transfer handle ownership to a legacy caller."""
        handle, self.handle = self.handle, None
        return handle

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.release()


@contextmanager
def open_grib_file(path):
    """Open a data file at the reki-owned observable boundary."""
    record_io_event("file_open_count")
    with reader_errors(path, "read_grib"), open(path, "rb", buffering=0) as handle:
        yield handle


def iter_headers(path: str | Path, *, headers_only=True):
    """Yield released-on-exit header records in file order.

    A record is also released when iteration advances or is closed early, so
    callers may use either ``with header`` or a simple predicate loop.
    """
    with open_grib_file(path) as file_handle:
        ordinal = 0
        previous = None
        try:
            while True:
                if previous is not None:
                    previous.release()
                    previous = None
                offset = file_handle.tell()
                message = eccodes.codes_grib_new_from_file(
                    file_handle,
                    headers_only=headers_only,
                )
                if message is None:
                    if ordinal == 0 and file_handle.seek(0, 2):
                        raise SourceError("decode_failed", "/source/path", "Nonempty input contains no GRIB messages", {"resource": str(path)})
                    return
                record_io_event("grib_header_scan_count")
                length = None
                try:
                    length = eccodes.codes_get(message, "totalLength")
                except eccodes.KeyValueNotFoundError:
                    pass
                previous = GribHeader(ordinal, offset, message, length)
                yield previous
                ordinal += 1
        finally:
            if previous is not None:
                previous.release()


def load_message_at_offset(path: str | Path, offset: int, *, headers_only=False):
    with open_grib_file(path) as file_handle:
        file_handle.seek(offset)
        message = eccodes.codes_grib_new_from_file(
            file_handle, headers_only=headers_only
        )
    return message


def decode_values(message, *, missing_value=None, fill_value=np.nan):
    """Decode in scan order, using encoded missingness instead of value equality."""
    bitmap = eccodes.codes_get_long(message, "bitmapPresent")
    complex_missing = (
        not bitmap
        and eccodes.codes_is_defined(message, "missingValueManagementUsed")
        and eccodes.codes_get_long(message, "missingValueManagementUsed") in {1, 2}
    )
    if complex_missing and fill_value is not None:
        eccodes.codes_set_double(message, "missingValue", float("nan"))
    elif missing_value is not None:
        eccodes.codes_set_double(message, "missingValue", missing_value)
    record_io_event("value_decode_count")
    values = eccodes.codes_get_double_array(message, "values")
    return fill_missing(message, values, fill_value)


def fill_missing(message, values, fill_value):
    if fill_value is None:
        return values
    if eccodes.codes_get_long(message, "bitmapPresent"):
        bitmap = eccodes.codes_get_long_array(message, "bitmap").reshape(values.shape)
        return np.where(bitmap, values, fill_value)
    if eccodes.codes_is_defined(message, "missingValueManagementUsed"):
        if eccodes.codes_get_long(message, "missingValueManagementUsed") in {1, 2}:
            return np.where(np.isnan(values), fill_value, values)
    return values
