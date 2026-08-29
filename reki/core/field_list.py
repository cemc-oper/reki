"""The small immutable lazy field collection public API."""

from collections.abc import Sequence

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
