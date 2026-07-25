"""GrADS reader bound to the ``reader()`` dispatch.

A GrADS dataset is a ``.ctl`` description file plus a raw binary data
file; the reader wraps the ctl path and delegates decoding to the
``reki.readers.grads.field`` kernel.
"""

import os
from typing import Dict, Optional

from reki.readers import Reader

from .field import load_field_from_file


class GradsReader(Reader):
    """Reader for GrADS ctl files.

    ``sel()`` only accumulates filter conditions (no I/O); decoding
    happens in ``to_xarray()``.
    """

    def __init__(self, source, path, filters: Optional[Dict] = None, **kwargs):
        super().__init__(source, path)
        self._filters = dict(filters) if filters else {}

    @property
    def filters(self) -> Dict:
        """The accumulated filter conditions (a copy)."""
        return dict(self._filters)

    def __repr__(self):
        return f"GradsReader({self.path!r}, filters={self._filters!r})"

    def sel(self, parameter: str = None, level_type: str = None,
            level=None, **kwargs) -> "GradsReader":
        """Return a new reader with more filter conditions (no I/O)."""
        filters = dict(self._filters)
        for key, value in (
                ("parameter", parameter),
                ("level_type", level_type),
                ("level", level),
        ):
            if value is not None:
                filters[key] = value
        filters.update(kwargs)
        return GradsReader(self.source, self.path, filters=filters)

    def to_xarray(self, **kwargs):
        filters = {**self._filters, **kwargs}
        if "parameter" not in filters:
            raise ValueError(
                "parameter is required to load a field from a GrADS file"
            )
        return load_field_from_file(self.path, **filters)


def READER(source, path, magic=None, deeper_check=False, **kwargs):
    """Claim GrADS ctl files by extension and the ``dset`` keyword."""
    if not os.path.splitext(str(path))[1].lower() == ".ctl":
        return None
    if magic is None:
        return None
    head = magic.lstrip().lower()
    if head.startswith(b"dset"):
        return GradsReader(source, path, **kwargs)
    if deeper_check and b"dset" in head:
        return GradsReader(source, path, **kwargs)
    return None
