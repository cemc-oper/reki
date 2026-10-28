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
class BranchEvent:
    """Internal acquisition progress, including branches that yield no fields.

    started precedes acquisition; exhausted follows complete retrieval AND checking
    of all previously yielded candidates for that branch. Shared physical scans
    may emit events for several branches without repeating their I/O. No counts,
    business completeness claims or new public report statuses are introduced.
    """

    query_index: int
    branch_index: int
    status: str

    def __post_init__(self):
        if (
            type(self.query_index) is not int
            or self.query_index < 0
            or type(self.branch_index) is not int
            or self.branch_index < 0
            or self.status not in {"started", "exhausted"}
        ):
            raise QueryError("invalid_config", "", "invalid backend branch event")


class BranchProgress:
    """One execution's progress; never retained by the source as a cache."""

    def __init__(self, plan):
        self._states = {
            (t["query_index"], b["index"]): "not_started"
            for t in plan.translations
            for b in t["branches"]
        }

    def _require(self, branch):
        if branch not in self._states:
            raise QueryError("invalid_config", "", "invalid backend branch reference")

    def started(self, branch):
        self._require(branch)
        if self._states[branch] == "exhausted":
            raise QueryError(
                "invalid_config", "", "candidate or start follows branch exhaustion"
            )
        self._states[branch] = "started"

    def update(self, event):
        branch = (event.query_index, event.branch_index)
        self._require(branch)
        if event.status == "started":
            self.started(branch)
        else:
            if self._states[branch] != "started":
                raise QueryError(
                    "invalid_config", "", "branch exhaustion requires a started branch"
                )
            self._states[branch] = "exhausted"

    def finish(self):
        # The Scan contract makes NORMAL iterator exhaustion a certification of
        # the whole planned range, even when a shared scan emitted no candidates.
        self._states = dict.fromkeys(self._states, "exhausted")

    def query_exhausted(self, index):
        return all(
            state == "exhausted"
            for (qi, _), state in self._states.items()
            if qi == index
        )

    def execution(self, branch):
        state = self._states[branch]
        return (
            {"status": "exhausted"}
            if state == "exhausted"
            else {
                "status": "stopped_early" if state == "started" else "not_started",
                "reason": "first_match_selected",
            }
        )


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
        if not isinstance(self.branches, (list, tuple)) or any(
            not isinstance(b, (list, tuple))
            or len(b) != 2
            or any(type(i) is not int or i < 0 for i in b)
            for b in self.branches
        ):
            raise QueryError("invalid_config", "", "invalid backend branch reference")
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
        """Return Scan with .plan, .context, FieldReference/BranchEvent iterator and close()."""

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
