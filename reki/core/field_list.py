"""The small immutable lazy field collection public API."""

from collections.abc import Sequence

import pandas as pd

from .errors import DataNotFoundError, MultipleFieldsMatchedError
from .field_query import FieldQuery, field_query_from_kwargs


class FieldList(Sequence):
    def __init__(self, fields=(), *, query=None, source_summary="<unknown source>"):
        self._fields = tuple(fields)
        self._query = query or FieldQuery()
        self._source_summary = source_summary

    @classmethod
    def from_fields(cls, fields):
        return cls(fields)

    @classmethod
    def concat(cls, *lists, deduplicate=False):
        fields = [field for values in lists for field in values]
        if deduplicate:
            seen, unique = set(), []
            for item in fields:
                key = (item.metadata.source, item.metadata.index, item.metadata.offset)
                if key not in seen:
                    seen.add(key); unique.append(item)
            fields = unique
        return cls(fields)

    def __len__(self):
        return len(self._fields)

    def __getitem__(self, item):
        if isinstance(item, slice):
            return type(self)(self._fields[item], query=self._query,
                              source_summary=self._source_summary)
        return self._fields[item]

    def all(self):
        return self

    def first(self):
        return self._fields[0] if self._fields else None

    def one(self):
        if not self._fields:
            raise DataNotFoundError(self._query, self._source_summary, 0)
        if len(self._fields) > 1:
            raise MultipleFieldsMatchedError(self._query, self._source_summary, len(self._fields))
        return self._fields[0]

    def one_or_none(self):
        return None if not self._fields else self.one()

    def sel(self, query=None, /, **kwargs):
        if query is not None and not isinstance(query, FieldQuery):
            raise TypeError("the positional argument to sel() must be a FieldQuery")
        if query is not None and kwargs:
            raise TypeError("FieldQuery and keyword filters cannot be mixed")
        query = self._query.merge(query or field_query_from_kwargs(kwargs))
        return type(self)((field for field in self if _matches(field.metadata, query)),
                          query=query, source_summary=self._source_summary)

    def where(self, query=None, /, **kwargs):
        """Safely filter metadata using a :class:`FieldQuery` or key values."""
        return self.sel(query, **kwargs)

    def metadata(self, keys=None):
        """Return stable metadata rows without materialising any field values."""
        if keys is None:
            keys = _DEFAULT_COLUMNS
        elif isinstance(keys, str):
            keys = tuple(key.strip() for key in keys.split(",") if key.strip())
        else:
            keys = tuple(keys)
        available = _KNOWN_KEYS | {key for field in self for key in field.metadata.extra}
        unknown = set(keys) - available
        if unknown:
            raise KeyError(f"unknown metadata key(s): {', '.join(sorted(unknown))}")
        rows = [{key: _metadata_value(field.metadata, key) for key in keys} for field in self]
        frame = pd.DataFrame(rows, columns=keys)
        for key in ("index", "offset", "member"):
            if key in frame:
                frame[key] = frame[key].astype("Int64")
        return frame

    def json(self, keys=None):
        """Return JSON-safe, deterministic metadata records."""
        frame = self.metadata(keys)
        return [_json_record(row) for row in frame.to_dict("records")]

    def unique(self, key):
        if key not in _KNOWN_KEYS:
            raise KeyError(f"unknown metadata key: {key}")
        values, seen = [], set()
        for field in self:
            value = _metadata_value(field.metadata, key)
            marker = repr(value)
            if marker not in seen:
                seen.add(marker)
                values.append(value)
        return values

    def head(self, n=5):
        if n < 0:
            raise ValueError("n must be non-negative")
        return self[:n]

    def summary(self):
        metadata = [field.metadata for field in self]
        return {
            "field_count": len(metadata),
            "parameter_count": len({m.parameter for m in metadata if m.parameter is not None}),
            "level_count": len({(m.level_type, m.level) for m in metadata if m.level is not None}),
            "member_count": len({m.member for m in metadata if m.member is not None}),
            "grid_count": len({m.grid_type for m in metadata if m.grid_type is not None}),
            "start_time": _time_bound(metadata, "start_time", min),
            "end_time": _time_bound(metadata, "valid_time", max),
        }

    def describe(self):
        result = self.summary()
        result["parameters"] = self.unique("parameter")
        result["level_types"] = self.unique("level_type")
        result["grid_types"] = self.unique("grid_type")
        return result

    def ls(self, keys=None):
        return self.metadata(keys)

    def to_xarray(self, **kwargs):
        from reki.readers.grib.reader import _merge_arrays
        return _merge_arrays([field.to_xarray(**kwargs) for field in self])

    def __repr__(self):
        sources = len({field.metadata.source for field in self})
        preview = ", ".join(
            f"{field.metadata.parameter}@{field.metadata.level_type}:{field.metadata.level}"
            for field in self[:10]
        )
        text = f"FieldList({len(self)} fields, {sources} sources; {preview})"
        return text if len(text) <= 2000 else text[:1997] + "..."


def _matches(metadata, query):
    pairs = (("parameter", metadata.parameter), ("level_type", metadata.level_type),
             ("level", metadata.level), ("step_type", metadata.step_type),
             ("time_range", metadata.time_range), ("member", metadata.member))
    for key, actual in pairs:
        expected = getattr(query, key)
        if expected is not None and actual not in (expected if isinstance(expected, tuple) else (expected,)):
            return False
    return all(metadata.extra.get(key) == value for key, value in query.extra.items())


_DEFAULT_COLUMNS = ("index", "parameter", "level_type", "level", "start_time",
                    "step", "valid_time", "step_type", "member", "grid_type")
_KNOWN_KEYS = frozenset(_DEFAULT_COLUMNS + ("offset", "time_range", "shape", "dtype", "source", "extra"))


def _metadata_value(metadata, key):
    if key in metadata.extra:
        return metadata.extra[key]
    return getattr(metadata, key)


def _time_bound(metadata, key, function):
    values = [getattr(item, key) for item in metadata if getattr(item, key) is not None]
    return None if not values else function(values)


def _json_record(row):
    def convert(value):
        if value is None:
            return None
        if not isinstance(value, (tuple, list, dict)) and pd.isna(value):
            return None
        if isinstance(value, pd.Timestamp):
            return value.isoformat().replace("+00:00", "Z")
        if isinstance(value, pd.Timedelta):
            return value.isoformat()
        if isinstance(value, (tuple, list)):
            return [convert(item) for item in value]
        return value
    return {key: convert(value) for key, value in row.items()}
