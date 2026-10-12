"""Evidence-limited public Query to existing parameter registry resolution."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from importlib.resources import files
from typing import Any, Mapping

import pandas as pd

from cedarkit_query import AliasSnapshot, Query, QueryError, expand_request

from .core import FieldQuery
from .readers.grib.config import (
    ParameterAmbiguityError,
    ParameterConditionConflictError,
    ParameterExternalNameNotMappedError,
    ParameterNotFoundError,
    ParameterNamespaceNotFoundError,
    resolve_external_name,
    resolve_parameter,
)

FROZEN_REGISTRY_SHA256 = "795f046b87d439dcf0e26d94587c20d3a0276bebda277df1db1fd251d5bfaabf"
FROZEN_DATASET = "cma_gfs_gmf_cmadaas"
FROZEN_REFERENCE_TIME = "2026-08-30T00:00:00Z"
FROZEN_LEAD_TIME = "PT86400S"
_CASES = {
    "cedarkit.t": ("TEM", "instant"),
    "cedarkit.h.any": ("GPH", "instant"),
    "cedarkit.rainc.any": ("CPE", "accum"),
    "cedarkit.rainnc.any": ("LPE", "accum"),
}
_ALLOWED_QUERY_FIELDS = {"api_version", "domain", "dataset", "parameter", "reference_time",
                         "lead_time", "vertical", "statistic"}


@dataclass(frozen=True)
class FrozenParameterResolution:
    """A checked single-field mapping; no file or service access is implied."""

    query: Query
    field_query: FieldQuery
    external_code: str
    registry_sha256: str


def _check_registry(registry_sha256: str) -> None:
    if not isinstance(registry_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", registry_sha256):
        raise QueryError("invalid_query", "/vocabulary_version", "registry SHA256 must be 64 lowercase hex digits")
    resource = files("reki.readers.grib.config").joinpath("param_registry.yaml")
    actual = hashlib.sha256(resource.read_bytes()).hexdigest()
    if actual != registry_sha256 or actual != FROZEN_REGISTRY_SHA256:
        raise QueryError("unsupported", "/vocabulary_version", "parameter registry differs from the T07 frozen snapshot")


def frozen_vocabulary_snapshot(*, registry_sha256: str) -> AliasSnapshot:
    """Build an explicit CMADaaS alias snapshot for the four verified cases."""
    _check_registry(registry_sha256)
    names: dict[str, str] = {}
    for parameter_id, (expected, _) in _CASES.items():
        resolved = resolve_external_name(parameter_id, "cmadaas")
        if resolved.code != expected or resolved.entry_parameter_id != parameter_id or resolved.inherited:
            raise QueryError("unsupported", "/vocabulary_version", "frozen external-name mapping changed")
        names[expected] = parameter_id
    return AliasSnapshot(registry_sha256, {"cmadaas": names})


def resolve_frozen_parameter(
    query: Query | Mapping[str, Any],
    *,
    registry_sha256: str,
    vocabulary_snapshot: AliasSnapshot | Mapping[str, Any] | None = None,
    catalog_snapshot: AliasSnapshot | Mapping[str, Any] | None = None,
) -> FrozenParameterResolution:
    """Resolve one frozen surface field through the existing registry.

    This checks the packaged snapshot and the full verified query shape before
    returning a legacy FieldQuery. It deliberately does not bind a service or
    convert data values or units.
    """
    _check_registry(registry_sha256)
    source = query.to_dict() if isinstance(query, Query) else query
    prepared = expand_request({"api_version": "cedarkit.request/v1", "action": "plan", "query": source},
                              vocabulary_snapshot=vocabulary_snapshot, catalog_snapshot=catalog_snapshot)
    if vocabulary_snapshot is not None:
        supplied = vocabulary_snapshot if isinstance(vocabulary_snapshot, AliasSnapshot) else AliasSnapshot(
            vocabulary_snapshot["version"], vocabulary_snapshot["aliases"])
        if supplied != frozen_vocabulary_snapshot(registry_sha256=registry_sha256):
            raise QueryError("unsupported", "/vocabulary_version", "alias snapshot differs from frozen evidence")
    if len(prepared.expanded_requests) != 1:
        raise QueryError("unsupported", "/query", "frozen parameter mapping requires one field")
    normalized = prepared.expanded_requests[0].query
    value = normalized.to_dict()
    extras = set(value) - _ALLOWED_QUERY_FIELDS
    if extras:
        name = sorted(extras)[0]
        raise QueryError("unsupported", f"/query/{name}", "field is outside the frozen mapping evidence")
    if value["dataset"] != FROZEN_DATASET:
        raise QueryError("unsupported", "/query/dataset", "dataset is outside the frozen mapping evidence")
    parameter = value["parameter"]
    try:
        external = resolve_external_name(parameter, "cmadaas")
    except ParameterNotFoundError as exc:
        raise QueryError("unknown_parameter", "/query/parameter", str(exc)) from exc
    except (ParameterExternalNameNotMappedError, ParameterNamespaceNotFoundError) as exc:
        raise QueryError("unmapped_parameter", "/query/parameter", str(exc)) from exc
    except ParameterAmbiguityError as exc:
        raise QueryError("ambiguous_mapping", "/query/parameter", str(exc)) from exc
    case = _CASES.get(parameter)
    if case is None:
        raise QueryError("unsupported", "/query/parameter", "parameter is outside the four frozen cases")
    code, statistic = case
    if external.code != code or external.entry_parameter_id != parameter or external.inherited:
        raise QueryError("unsupported", "/query/parameter", "external-name mapping differs from frozen evidence")
    if value.get("reference_time") != FROZEN_REFERENCE_TIME:
        raise QueryError("unsupported", "/query/reference_time", "reference time is outside the frozen evidence")
    if value.get("lead_time") != FROZEN_LEAD_TIME:
        raise QueryError("unsupported", "/query/lead_time", "lead time is outside the frozen evidence")
    if value.get("vertical") != {"type": "surface"}:
        raise QueryError("unsupported", "/query/vertical", "only the verified surface field is supported")
    expected_statistic = {"kind": statistic}
    if statistic == "accum":
        expected_statistic["window"] = FROZEN_LEAD_TIME
    if value.get("statistic") != expected_statistic:
        raise QueryError("unsupported", "/query/statistic", "statistic or accumulation window differs from evidence")
    try:
        resolved = resolve_parameter(
            parameter, level_type="surface", step_type=statistic,
            time_range=pd.Timedelta(hours=24) if statistic == "accum" else None,
            extra={"typeOfFirstFixedSurface": 1},
        )
    except ParameterConditionConflictError as exc:
        raise QueryError("unsupported", "/query/parameter", str(exc)) from exc
    if resolved.record.parameter_id != parameter:
        raise QueryError("unsupported", "/query/parameter", "resolved record differs from requested stable ID")
    return FrozenParameterResolution(normalized, resolved.query, code, registry_sha256)
