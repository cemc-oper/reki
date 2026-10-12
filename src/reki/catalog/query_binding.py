"""Explicit catalog snapshots and pure grid-query source binding plans."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from string import Formatter
from typing import Any, Mapping

from cedarkit_query import AliasSnapshot, Binding, Query, QueryError, binding_identity, normalize_request, query_identity

from .loader import _builtin_path, load_catalog
from .model import Catalog, ResolvedDataset

_TEMPLATE_FIELDS = {"start_time_label", "forecast_hour", "forecast_hour_label"}


@dataclass(frozen=True)
class CatalogSnapshot:
    """An already selected catalog plus its caller-controlled immutable version."""

    catalog: Catalog
    version: str

    def __post_init__(self) -> None:
        if not isinstance(self.catalog, Catalog):
            raise TypeError("catalog must be a Catalog")
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("catalog version must be a non-empty string")

    def aliases(self) -> AliasSnapshot:
        names = {alias: dataset_id for dataset_id, record in self.catalog.records.items()
                 for alias in record.aliases}
        return AliasSnapshot(self.version, {"reki-catalog": names})


@dataclass(frozen=True)
class BindingPlan:
    """Controlled binding and safe display metadata; no availability claim."""

    query: Query
    binding: Binding
    query_id: str
    binding_id: str
    catalog_version: str
    origin: str
    replaced_origins: tuple[str, ...]

    def to_display_dict(self) -> dict[str, Any]:
        """Return a deliberately non-executable, path-free plan summary."""
        source = self.binding.to_dict()
        return {
            "query_id": self.query_id,
            "binding_id": self.binding_id,
            "dataset": source["dataset"],
            "kind": source["kind"],
            "catalog_version": self.catalog_version,
            "origin": _origin_label(self.origin),
            "replaced_origins": [_origin_label(item) for item in self.replaced_origins],
            "locator_redacted": source["kind"] == "local",
        }


def _origin_label(value: str) -> str:
    if value.startswith("user:"):
        return "user"
    if value.startswith("plugin "):
        return "plugin"
    return value


def builtin_catalog_snapshot() -> CatalogSnapshot:
    """Explicitly load only the packaged catalog; no plugins or user config."""
    digest = hashlib.sha256(_builtin_path().read_bytes()).hexdigest()
    return CatalogSnapshot(load_catalog(plugins=False, user=False), f"sha256:{digest}")


def _template(value: str, path: str) -> None:
    if not isinstance(value, str) or not value:
        raise QueryError("invalid_query", path, "non-empty template string required")
    try:
        fields = list(Formatter().parse(value))
    except ValueError as exc:
        raise QueryError("invalid_query", path, "malformed file pattern template") from exc
    for _, field, format_spec, conversion in fields:
        if field is not None and (field not in _TEMPLATE_FIELDS or format_spec or conversion):
            raise QueryError("unsupported", path, "file pattern uses an unsupported template field")


def _binding(resolved: ResolvedDataset, version: str, local_config_version: str | None) -> Binding:
    source = resolved.source
    base: dict[str, Any] = {
        "api_version": "cedarkit.binding/v1", "dataset": resolved.record.dataset_id,
        "source_id": f"reki:{source.name}", "catalog_version": version, "origin": resolved.origin,
    }
    if source.name == "cmadaas":
        if source.args or set(source.kwargs) != {"kind", "data_code"} or source.kwargs["kind"] != "model_grid":
            raise QueryError("unsupported", "/binding", "CMADaaS source has unmapped arguments")
        base.update(kind="cmadaas", data_code=source.kwargs["data_code"], request_kind="model_grid")
    elif source.name == "local":
        if len(source.args) != 1 or not isinstance(source.args[0], str) or not source.args[0] or source.kwargs:
            raise QueryError("unsupported", "/binding", "local source has unmapped arguments")
        data_type = source.args[0]
        if data_type.startswith("/") or "\\" in data_type or any(
            part in ("", ".", "..") for part in data_type.split("/")
        ):
            raise QueryError("unsupported", "/binding/locator/data_type", "local data type must be a relative config key")
        if not isinstance(local_config_version, str) or not local_config_version:
            raise QueryError("unsupported", "/binding/locator/config_version",
                             "local source needs an explicit configuration version")
        base.update(kind="local", locator={"resolver": "reki-local", "data_type": data_type,
                                           "config_version": local_config_version})
    elif source.name == "file-pattern":
        if len(source.args) != 2 or source.kwargs:
            raise QueryError("unsupported", "/binding", "file-pattern source has unmapped arguments")
        root, pattern = source.args
        _template(root, "/binding/locator/root")
        _template(pattern, "/binding/locator/pattern")
        base.update(kind="local", locator={"resolver": "file-pattern", "root": root, "pattern": pattern})
    else:
        raise QueryError("unsupported", "/binding/kind", "source kind has no v1 Binding mapping")
    return Binding(base)


def plan_source_binding(
    query: Query | Mapping[str, Any],
    *,
    snapshot: CatalogSnapshot,
    local_config_version: str | None = None,
    vocabulary_snapshot: AliasSnapshot | Mapping[str, Any] | None = None,
) -> BindingPlan:
    """Resolve a logical dataset only against the supplied catalog snapshot."""
    if not isinstance(snapshot, CatalogSnapshot):
        raise TypeError("snapshot must be a CatalogSnapshot")
    source = query.to_dict() if isinstance(query, Query) else query
    prepared = normalize_request({"api_version": "cedarkit.request/v1", "action": "validate", "query": source},
                                 catalog_snapshot=snapshot.aliases(), vocabulary_snapshot=vocabulary_snapshot)
    normalized = prepared.normalized_request.query
    dataset_id = normalized.dataset
    if dataset_id not in snapshot.catalog.records:
        raise QueryError("unknown_dataset", "/query/dataset", "dataset is absent from the supplied catalog snapshot")
    resolved = snapshot.catalog.resolve(dataset_id)
    binding = _binding(resolved, snapshot.version, local_config_version)
    return BindingPlan(normalized, binding, query_identity(normalized), binding_identity(binding),
                       snapshot.version, resolved.origin, resolved.replaced_origins)
