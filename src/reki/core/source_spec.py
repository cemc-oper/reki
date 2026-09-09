"""Serializable, immutable descriptions of a reki source."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from math import isfinite
from pathlib import Path
from types import MappingProxyType
from typing import Any, Hashable, Mapping


_SENSITIVE_KEYS = frozenset({
    "password", "passwd", "token", "secret", "api_key", "access_key",
    "secret_key", "authorization",
})


def _freeze(value: Any, path: str = "value") -> Any:
    if value is None or isinstance(value, (bool, str, int, bytes, Path, datetime,
                                           date, timedelta)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise TypeError(f"{path}: non-finite floats are not supported")
        return value
    # pandas is deliberately duck-typed here to keep this low-level module light.
    if value.__class__.__module__.startswith("pandas") and value.__class__.__name__ in {"Timestamp", "Timedelta"}:
        return value
    if isinstance(value, Mapping):
        return MappingProxyType({_freeze(k, f"{path}.<key>"): _freeze(v, f"{path}.{k}") for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v, f"{path}[{i}]") for i, v in enumerate(value))
    if isinstance(value, (set, frozenset)):
        raise TypeError(f"{path}: sets are not supported because their order is not stable")
    raise TypeError(f"{path}: unsupported value type {type(value).__name__}")


def _key(value: Any, path: str = "value") -> Hashable:
    """Produce a typed, deterministic key; never fall back to repr/address."""
    if value is None:
        return ("none",)
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, str):
        return ("str", value)
    if isinstance(value, int):
        return ("int", value)
    if isinstance(value, float):
        return ("float", value)
    if isinstance(value, bytes):
        return ("bytes", value)
    if isinstance(value, Path):
        return ("path", str(value))
    if isinstance(value, datetime):
        return ("datetime", value.isoformat())
    if isinstance(value, date):
        return ("date", value.isoformat())
    if isinstance(value, timedelta):
        return ("timedelta", value.total_seconds())
    if value.__class__.__module__.startswith("pandas"):
        return (value.__class__.__name__, str(value))
    if isinstance(value, Mapping):
        return ("mapping", tuple(sorted((_key(k, f"{path}.<key>"), _key(v, f"{path}.{k}")) for k, v in value.items())))
    if isinstance(value, tuple):
        return ("tuple", tuple(_key(v, f"{path}[{i}]") for i, v in enumerate(value)))
    raise TypeError(f"{path}: unsupported value type {type(value).__name__}")


def redact(value: Any, key_name: str | None = None) -> Any:
    """Return a recursively redacted display value without changing the value."""
    if key_name is not None and key_name.lower() in _SENSITIVE_KEYS:
        return "***"
    if isinstance(value, Mapping):
        return {k: redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, tuple):
        return tuple(redact(v) for v in value)
    return value


@dataclass(frozen=True)
class SourceSpec:
    name: str
    args: tuple = ()
    kwargs: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name:
            raise TypeError("name must be a non-empty string")
        object.__setattr__(self, "name", self.name.replace("_", "-"))
        object.__setattr__(self, "args", tuple(_freeze(v, f"args[{i}]") for i, v in enumerate(self.args)))
        if not isinstance(self.kwargs, Mapping):
            raise TypeError("kwargs must be a mapping")
        object.__setattr__(self, "kwargs", _freeze(self.kwargs, "kwargs"))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SourceSpec":
        if not isinstance(value, Mapping):
            raise TypeError("SourceSpec input must be a mapping")
        unknown = set(value) - {"name", "args", "kwargs"}
        if unknown:
            raise TypeError(f"unknown SourceSpec fields: {', '.join(sorted(unknown))}")
        if "name" not in value:
            raise TypeError("SourceSpec input requires 'name'")
        return cls(value["name"], tuple(value.get("args", ())), value.get("kwargs", {}))

    def normalized_key(self) -> Hashable:
        return ("SourceSpec", _key(self.name, "name"), _key(self.args, "args"), _key(self.kwargs, "kwargs"))

    def __repr__(self) -> str:
        return f"SourceSpec(name={self.name!r}, args={redact(self.args)!r}, kwargs={redact(self.kwargs)!r})"
