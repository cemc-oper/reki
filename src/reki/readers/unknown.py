"""Fallback reader for files no other reader claims."""

from . import Reader


class UnknownReader(Reader):
    """Keep the raw bytes of a file of unknown format.

    Never raises on creation; conversions to xarray/pandas/numpy are
    not supported and raise ``NotImplementedError`` from the base class.
    """

    def to_bytes(self) -> bytes:
        with open(self.path, "rb") as f:
            return f.read()
