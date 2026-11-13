"""Shared ecCodes I/O with no legacy-reader or cfgrib imports."""

from contextlib import contextmanager
from dataclasses import dataclass
from os import fstat
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
        yield from _iter_eccodes_headers(file_handle, path, headers_only=headers_only)


def _iter_eccodes_headers(stream, path, *, headers_only=True, ordinal=0):
    while True:
        offset = stream.tell()
        message = eccodes.codes_grib_new_from_file(stream, headers_only=headers_only)
        if message is None:
            if ordinal == 0 and stream.seek(0, 2):
                raise SourceError(
                    "decode_failed",
                    "/source/path",
                    "Nonempty input contains no GRIB messages",
                    {"resource": str(path)},
                )
            return
        record_io_event("grib_header_scan_count")
        with GribHeader(ordinal, offset, message) as record:
            try:
                record.message_length = eccodes.codes_get(message, "totalLength")
            except eccodes.KeyValueNotFoundError:
                pass
            yield record
        ordinal += 1


def iter_grib2_headers(path):
    """Skip packed values for contiguous single-field GRIB2 messages."""
    with open_grib_file(path) as stream:
        size = fstat(stream.fileno()).st_size
        offset = ordinal = 0
        prefix = stream.read(min(1024, size))
        while offset < size:
            header = _grib2_header(stream, offset, size, prefix)
            if header is None:
                break
            metadata, length = header
            end = offset + length
            stream.seek(end - 4)
            following = stream.read(4 + min(1024, size - end))
            if following[:4] != b"7777":
                break
            try:
                handle = eccodes.codes_new_from_message(metadata)
            except eccodes.CodesInternalError:
                break
            record_io_event("grib_header_scan_count")
            with GribHeader(ordinal, offset, handle, length) as record:
                yield record
            ordinal += 1
            offset, prefix = end, following[4:]
        if offset < size:
            # Keep ecCodes' regular framing and error handling for other streams.
            stream.seek(offset)
            yield from _iter_eccodes_headers(stream, path, ordinal=ordinal)


def _grib2_header(stream, offset, size, prefix):
    if len(prefix) < 16 or prefix[:4] != b"GRIB" or prefix[7] != 2:
        return None
    length = int.from_bytes(prefix[8:16], "big")
    if not 20 <= length <= size - offset:
        return None
    cursor, sections = 16, []
    while cursor + 5 <= length - 4:
        section = prefix[cursor:cursor + 5]
        if len(section) != 5:
            stream.seek(offset + cursor)
            section = stream.read(5)
            if len(section) != 5:
                return None
        section_length = int.from_bytes(section[:4], "big")
        sections.append(section[4])
        if section_length < 5 or cursor + section_length > length - 4:
            return None
        if section[4] == 7:
            break
        cursor += section_length
    else:
        return None
    if sections not in ([1, 3, 4, 5, 6, 7], [1, 2, 3, 4, 5, 6, 7]):
        return None
    if cursor + section_length != length - 4:
        return None
    header = prefix[:cursor]
    if len(header) < cursor:
        stream.seek(offset + len(header))
        header += stream.read(cursor - len(header))
        if len(header) != cursor:
            return None
    # Sections 0–6 carry the selection metadata. The locator keeps the real length.
    return (
        header[:8]
        + (cursor + 9).to_bytes(8, "big")
        + header[16:]
        + b"\x00\x00\x00\x05\x07"
        + b"7777",
        length,
    )


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
