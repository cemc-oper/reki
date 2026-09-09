"""The immutable public description of a requested field."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Mapping
import pandas as pd
from .source_spec import _freeze, redact

_STANDARD = frozenset({"parameter", "level_type", "level", "step_type", "time_range", "member"})

@dataclass(frozen=True)
class FieldQuery:
    parameter: Any = None
    level_type: Any = None
    level: Any = None
    step_type: str | None = None
    time_range: pd.Timedelta | None = None
    member: Any = None
    extra: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        for name in ("parameter", "level_type", "level", "member"):
            value = getattr(self, name)
            if name in {"level", "member"} and isinstance(value, list):
                value = tuple(value)
            object.__setattr__(self, name, _freeze(value, name))
        if self.time_range is not None:
            object.__setattr__(self, "time_range", pd.Timedelta(self.time_range))
        if not isinstance(self.extra, Mapping):
            raise TypeError("extra must be a mapping")
        conflict = _STANDARD & set(self.extra)
        if conflict:
            raise TypeError(f"extra conflicts with standard query fields: {', '.join(sorted(conflict))}")
        object.__setattr__(self, "extra", _freeze(self.extra, "extra"))

    def merge(self, other: "FieldQuery") -> "FieldQuery":
        if not isinstance(other, FieldQuery):
            raise TypeError("can only merge a FieldQuery")
        values = {name: getattr(self, name) for name in _STANDARD}
        for name in _STANDARD:
            value = getattr(other, name)
            if value is not None:
                values[name] = value
        extra = dict(self.extra)
        extra.update({k: v for k, v in other.extra.items() if v is not None})
        return FieldQuery(**values, extra=extra)

    def __repr__(self):
        # A bounded repr keeps errors useful even for generated queries.
        text = f"FieldQuery(parameter={redact(self.parameter)!r}, level_type={redact(self.level_type)!r}, level={redact(self.level)!r}, extra={redact(self.extra)!r})"
        return text if len(text) <= 500 else text[:497] + "..."

def field_query_from_kwargs(kwargs: Mapping[str, Any]) -> FieldQuery:
    values = dict(kwargs)
    standard = {key: values.pop(key) for key in list(values) if key in _STANDARD}
    return FieldQuery(**standard, extra=values)
