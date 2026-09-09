"""Strict DatasetCatalog v1 parser and precedence-aware loader."""

from __future__ import annotations

import os
from importlib.metadata import entry_points
from pathlib import Path
from typing import Iterable, Mapping

import yaml

from reki.core import SourceSpec
from .model import Catalog, DatasetRecord


API_VERSION = "reki.catalog/v1"
ENTRY_POINT_GROUP = "reki.catalogs"
_TOP_LEVEL_FIELDS = frozenset({"api_version", "datasets"})
_DATASET_FIELDS = frozenset({"id", "aliases", "source", "metadata"})


class CatalogError(ValueError):
    """A deterministic catalog schema, plugin, or conflict error."""


def default_user_catalog_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    return Path(base) / "reki/catalog.yaml" if base else Path.home() / ".config/reki/catalog.yaml"


def _load_document(value, origin: str) -> list[DatasetRecord]:
    if isinstance(value, (str, Path)):
        path = Path(value)
        try:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise CatalogError(f"{origin}: cannot read catalog: {exc}") from exc
        except yaml.YAMLError as exc:
            raise CatalogError(f"{origin}: invalid YAML: {exc}") from exc
    if not isinstance(value, Mapping):
        raise CatalogError(f"{origin}: catalog must be a mapping")
    unknown = set(value) - _TOP_LEVEL_FIELDS
    if unknown:
        raise CatalogError(f"{origin}: unknown catalog fields: {', '.join(sorted(unknown))}")
    if value.get("api_version") != API_VERSION:
        raise CatalogError(f"{origin}: unsupported api_version {value.get('api_version')!r}")
    datasets = value.get("datasets")
    if not isinstance(datasets, list):
        raise CatalogError(f"{origin}: datasets must be a list")
    records = []
    ids, aliases = set(), set()
    for index, item in enumerate(datasets):
        if not isinstance(item, Mapping):
            raise CatalogError(f"{origin}: datasets[{index}] must be a mapping")
        unknown = set(item) - _DATASET_FIELDS
        if unknown:
            raise CatalogError(f"{origin}: datasets[{index}] has unknown fields: {', '.join(sorted(unknown))}")
        dataset_id = item.get("id")
        if not isinstance(dataset_id, str) or not dataset_id:
            raise CatalogError(f"{origin}: datasets[{index}].id must be a non-empty string")
        if dataset_id in ids or dataset_id in aliases:
            raise CatalogError(f"{origin}: duplicate dataset id {dataset_id!r}")
        raw_aliases = item.get("aliases", [])
        if not isinstance(raw_aliases, list) or any(not isinstance(x, str) or not x for x in raw_aliases):
            raise CatalogError(f"{origin}: datasets[{index}].aliases must be a list of non-empty strings")
        if len(set(raw_aliases)) != len(raw_aliases) or dataset_id in raw_aliases or aliases.intersection(raw_aliases):
            raise CatalogError(f"{origin}: duplicate dataset alias")
        if "source" not in item:
            raise CatalogError(f"{origin}: datasets[{index}].source is required")
        if not isinstance(item.get("metadata", {}), Mapping):
            raise CatalogError(f"{origin}: datasets[{index}].metadata must be a mapping")
        try:
            source = SourceSpec.from_dict(item["source"])
        except (TypeError, ValueError) as exc:
            raise CatalogError(f"{origin}: datasets[{index}].source: {exc}") from exc
        ids.add(dataset_id)
        aliases.update(raw_aliases)
        records.append(DatasetRecord(dataset_id, source, tuple(raw_aliases), item.get("metadata", {})))
    return records


def _builtin_path() -> Path:
    return Path(__file__).with_name("builtin") / "catalog.yaml"


def _plugin_layers() -> Iterable[tuple[str, object]]:
    points = sorted(entry_points(group=ENTRY_POINT_GROUP), key=lambda ep: (ep.dist.name if ep.dist else "", ep.name))
    for point in points:
        label = f"plugin {point.dist.name if point.dist else '<unknown>'}:{point.name}"
        try:
            loaded = point.load()
            yield label, loaded() if callable(loaded) else loaded
        except Exception as exc:
            raise CatalogError(f"{label}: cannot load catalog: {exc}") from exc


def load_catalog(*, builtin: bool = True, plugins: bool = True, user: bool = True,
                 user_path: str | Path | None = None, explicit: object | None = None) -> Catalog:
    """Load and merge catalog layers using the T2-01 precedence contract."""
    layers = []
    if builtin:
        layers.append(("builtin", _builtin_path()))
    if plugins:
        layers.extend(_plugin_layers())
    if user:
        configured = Path(user_path or os.environ.get("REKI_CATALOG_PATH", default_user_catalog_path()))
        if configured.exists():
            layers.append((f"user:{configured}", configured))
    if explicit is not None:
        layers.append(("explicit", explicit))

    records, origins, replaced = {}, {}, {}
    for origin, raw_layer in layers:
        for record in _load_document(raw_layer, origin):
            # A replacement is whole-record only.  A new alias may not steal
            # an alias still exposed by another canonical record.
            for other_id, other in records.items():
                if other_id != record.dataset_id and set(record.aliases).intersection(other.aliases):
                    raise CatalogError(f"{origin}: alias conflicts with active dataset {other_id!r}")
                if other_id != record.dataset_id and record.dataset_id in other.aliases:
                    raise CatalogError(f"{origin}: dataset id conflicts with active alias")
            if record.dataset_id in records:
                replaced.setdefault(record.dataset_id, []).append(origins[record.dataset_id])
            records[record.dataset_id] = record
            origins[record.dataset_id] = origin
    return Catalog(records, origins, replaced)
