"""Context-local I/O metrics used by reki readers.

The module deliberately has no logging side effects.  It is an internal
observation boundary which is also safe for applications to use when timing a
single operation.
"""

from collections import Counter
from contextvars import ContextVar
from dataclasses import dataclass
from types import MappingProxyType


_COUNTERS = (
    "source_resolve_count", "file_open_count", "grib_header_scan_count",
    "value_decode_count", "index_hit_count", "index_miss_count",
    "index_build_count", "index_rebuild_count",
)
_REASONS = frozenset((
    "absent", "stale", "corrupt", "schema", "decoder", "disabled",
    "unwritable", "source_changed", "lock_timeout",
))
_CURRENT: ContextVar["IOMetrics | None"] = ContextVar("reki_io_metrics", default=None)


@dataclass(frozen=True)
class IOMetricsSnapshot:
    """Immutable versioned counters captured from one collection context."""

    schema_version: int
    counters: MappingProxyType
    index_miss_reasons: MappingProxyType

    def __getitem__(self, key):
        return self.counters[key]

    def to_dict(self):
        return {"schema_version": self.schema_version, **dict(self.counters),
                "index_miss_reasons": dict(self.index_miss_reasons)}


class IOMetrics:
    def __init__(self):
        self._counters = Counter({key: 0 for key in _COUNTERS})
        self._reasons = Counter()
        self._token = None

    def __enter__(self):
        self._token = _CURRENT.set(self)
        return self

    def __exit__(self, exc_type, exc, traceback):
        _CURRENT.reset(self._token)
        self._token = None

    def snapshot(self):
        return IOMetricsSnapshot(1, MappingProxyType(dict(self._counters)),
                                 MappingProxyType(dict(self._reasons)))


def collect_io_metrics():
    """Collect events in this context; nested collectors own nested events."""
    return IOMetrics()


def record_io_event(name, *, reason=None):
    """Record one event in the innermost collector, if any."""
    collector = _CURRENT.get()
    if collector is None:
        return
    if name not in _COUNTERS:
        raise ValueError(f"unknown I/O metric: {name}")
    collector._counters[name] += 1
    if name == "index_miss_count" and reason is not None:
        if reason not in _REASONS:
            raise ValueError(f"unknown index miss reason: {reason}")
        collector._reasons[reason] += 1
