"""GrADS reader bound to the ``reader()`` dispatch.

A GrADS dataset is a ``.ctl`` description file plus a raw binary data
file; the reader wraps the ctl path and delegates decoding to the
``reki.readers.grads.field`` kernel.
"""

import os
from typing import Dict, Optional

from reki.readers import Reader
from reki.core import FieldQuery
from reki.core.field_query import field_query_from_kwargs

from .field import load_field_from_file


class GradsReader(Reader):
    """Reader for GrADS ctl files.

    ``sel()`` only accumulates filter conditions (no I/O); decoding
    happens in ``to_xarray()``.
    """

    def __init__(self, source, path, filters: Optional[Dict] = None, **kwargs):
        super().__init__(source, path)
        self._query = field_query_from_kwargs(filters or {})

    @property
    def filters(self) -> Dict:
        """The accumulated filter conditions (a copy)."""
        filters = dict(self._query.extra)
        for key in ("parameter", "level_type", "level"):
            value = getattr(self._query, key)
            if value is not None:
                filters[key] = list(value) if key == "level" and isinstance(value, tuple) else value
        return filters

    def __repr__(self):
        return f"GradsReader({self.path!r}, filters={self._filters!r})"

    def sel(self, query: FieldQuery = None, /, **kwargs) -> "GradsReader":
        """Return a new reader with more filter conditions (no I/O)."""
        if query is not None and not isinstance(query, FieldQuery):
            raise TypeError("the positional argument to sel() must be a FieldQuery")
        if query is not None and kwargs:
            raise TypeError("FieldQuery and keyword filters cannot be mixed")
        query = query if query is not None else field_query_from_kwargs(kwargs)
        merged = self._query.merge(query)
        return GradsReader(self.source, self.path, filters={**dict(merged.extra), **{k: getattr(merged, k) for k in ("parameter", "level_type", "level") if getattr(merged, k) is not None}})

    def to_xarray(self, **kwargs):
        filters = {**self.filters, **kwargs}
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
