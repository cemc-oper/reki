"""Immutable public metadata describing one field without its values."""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

import pandas as pd

from .source_spec import _freeze


def _freeze_extra(value):
    frozen = _freeze(value, "extra")
    return MappingProxyType(dict(frozen)) if hasattr(frozen, "items") else frozen


@dataclass(frozen=True)
class FieldMetadata:
    index: int
    offset: int | None
    parameter: str | None
    level_type: str | None
    level: int | float | None
    start_time: pd.Timestamp | None = None
    step: pd.Timedelta | None = None
    valid_time: pd.Timestamp | None = None
    step_type: str | None = None
    time_range: pd.Timedelta | None = None
    member: int | None = None
    shape: tuple[int, ...] | None = None
    dtype: str | None = None
    grid_type: str | None = None
    source: str = ""
    extra: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "extra", _freeze_extra(self.extra))
        for key in ("start_time", "valid_time"):
            value = getattr(self, key)
            if value is not None:
                object.__setattr__(self, key, pd.Timestamp(value))
        for key in ("step", "time_range"):
            value = getattr(self, key)
            if value is not None:
                object.__setattr__(self, key, pd.Timedelta(value))
        if self.shape is not None:
            object.__setattr__(self, "shape", tuple(self.shape))

    def to_dict(self):
        def timestamp(value):
            if value is None:
                return None
            value = pd.Timestamp(value)
            if value.tzinfo is None:
                value = value.tz_localize("UTC")
            return value.tz_convert("UTC").isoformat().replace("+00:00", "Z")
        return {
            "index": self.index, "offset": self.offset, "parameter": self.parameter,
            "level_type": self.level_type, "level": self.level,
            "start_time": timestamp(self.start_time),
            "step": None if self.step is None else self.step.value,
            "valid_time": timestamp(self.valid_time), "step_type": self.step_type,
            "time_range": None if self.time_range is None else self.time_range.value,
            "member": self.member, "shape": None if self.shape is None else list(self.shape),
            "dtype": self.dtype, "grid_type": self.grid_type, "source": self.source,
            "extra": dict(self.extra),
        }
