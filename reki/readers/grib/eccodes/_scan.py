"""The single ecCodes header scanning boundary for local GRIB files."""

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import eccodes

from reki.diagnostics import record_io_event


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
    with open(path, "rb") as handle:
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
                    file_handle, headers_only=headers_only,
                )
                if message is None:
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
