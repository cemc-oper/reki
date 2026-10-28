"""Internal I05/I06 boundary. Implementations must not infer business definitions.

plan is pure; start performs discovery/acquisition and returns a closeable Scan.
Scan.plan may refine pending translations using acquired facts, before iteration.
Every yielded reference is in stable SOURCE order, with snapshot-bound identity.
Normal iterator exhaustion certifies complete acquisition, including pagination;
truncation, metadata interpretation and decoding failures MUST raise SourceError.
No production backend is registered by I05.
"""

from dataclasses import dataclass
from collections.abc import Callable, Mapping
from typing import Protocol

from cedarkit_query import Query, normalize_query, expand_queries, QueryError

from reki.catalog.model import freeze, thaw


@dataclass(frozen=True)
class Plan:
    translations: tuple
    # One finite, complete expected identity set per effective Query, or None.
    # These sets require applicability evidence; observed fields are NOT a basis.
    expected: tuple

    def __post_init__(self):
        object.__setattr__(self, "translations", freeze(self.translations))
        object.__setattr__(self, "expected", freeze(self.expected))


@dataclass(frozen=True)
class FieldReference:
    # Reliable source/version/location identity, NOT a business identity or values.
    record_id: str
    identity: Query
    metadata: Mapping
    grid: Mapping
    load: Callable
    branches: tuple  # (query_index, branch_index), local to this execution plan

    def __post_init__(self):
        if not isinstance(self.record_id, str) or not self.record_id:
            raise QueryError("invalid_config", "", "backend record identity required")
        identity = normalize_query(self.identity)
        rows = expand_queries([identity])
        if len(rows) != 1 or rows[0].to_dict() != identity.to_dict():
            raise QueryError("invalid_config", "", "field identity must be scalar")
        # Continuous selectors do not expand; actual references cannot contain them.
        if not is_concrete(identity.to_dict()):
            raise QueryError("invalid_config", "", "field identity must be concrete")
        object.__setattr__(self, "identity", identity)
        object.__setattr__(self, "metadata", freeze(self.metadata))
        object.__setattr__(self, "grid", freeze(self.grid))
        object.__setattr__(self, "branches", tuple(tuple(b) for b in self.branches))


class Backend(Protocol):
    def plan(self, queries: tuple, configuration) -> Plan:
        """Pure translation and evidence-based expected sets; no business I/O."""

    def start(self, plan: Plan):
        """Return Scan with .plan, .context, iterator of FieldReference and close()."""

    def close(self):
        """Close owned resources only; NEVER close an externally injected client."""


class UnavailableBackend:
    """An explicit pending boundary, never a successful empty backend."""

    def plan(self, queries, configuration):
        return Plan(
            tuple(
                {
                    "query_index": i,
                    "coverage": {
                        "status": "pending",
                        "message": "I06 backend is not registered",
                    },
                    "branches": [],
                    "checks": [],
                }
                for i, _ in enumerate(queries)
            ),
            tuple(None for _ in queries),
        )

    def start(self, plan):
        raise QueryError(
            "unsupported",
            "/source",
            "I06 backend is not registered",
            {"stage": "selection", "reason": "translation_unavailable"},
        )

    def close(self):
        pass


def plan_dict(plan):
    return thaw(plan.translations)


def is_concrete(value):
    if isinstance(value, Mapping):
        return "range" not in value and all(is_concrete(v) for v in value.values())
    return not isinstance(value, (list, tuple))
