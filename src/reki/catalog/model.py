"""Immutable public models for DatasetCatalog v1."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from reki.core import SourceSpec


@dataclass(frozen=True)
class DatasetRecord:
    """One logical dataset and its source binding."""

    dataset_id: str
    source: SourceSpec
    aliases: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.dataset_id, str) or not self.dataset_id:
            raise TypeError("dataset_id must be a non-empty string")
        if not isinstance(self.source, SourceSpec):
            raise TypeError("source must be a SourceSpec")
        aliases = tuple(self.aliases)
        if any(not isinstance(alias, str) or not alias for alias in aliases):
            raise TypeError("aliases must contain non-empty strings")
        if self.dataset_id in aliases or len(set(aliases)) != len(aliases):
            raise ValueError("dataset aliases must be unique and cannot equal dataset_id")
        object.__setattr__(self, "aliases", aliases)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class ResolvedDataset:
    """Resolved source and the winning catalog layer diagnostic."""

    record: DatasetRecord
    source: SourceSpec
    origin: str
    replaced_origins: tuple[str, ...] = ()


@dataclass(frozen=True)
class Catalog:
    """An immutable merged catalog."""

    records: Mapping[str, DatasetRecord]
    origins: Mapping[str, str]
    replaced_origins: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "records", MappingProxyType(dict(self.records)))
        object.__setattr__(self, "origins", MappingProxyType(dict(self.origins)))
        object.__setattr__(self, "replaced_origins", MappingProxyType(
            {key: tuple(value) for key, value in self.replaced_origins.items()}
        ))
        aliases = {}
        for dataset_id, record in self.records.items():
            for alias in record.aliases:
                if alias in self.records and alias != dataset_id:
                    raise ValueError(f"catalog alias {alias!r} conflicts with dataset id")
                previous = aliases.setdefault(alias, dataset_id)
                if previous != dataset_id:
                    raise ValueError(f"catalog alias {alias!r} is ambiguous")
        object.__setattr__(self, "_aliases", MappingProxyType(aliases))

    def list(self) -> tuple[DatasetRecord, ...]:
        return tuple(self.records[key] for key in sorted(self.records))

    def show(self, dataset_id: str) -> ResolvedDataset:
        return self.resolve(dataset_id)

    def resolve(self, dataset_id: str) -> ResolvedDataset:
        canonical_id = dataset_id if dataset_id in self.records else self._aliases.get(dataset_id)
        if canonical_id is None:
            raise KeyError(f"unknown dataset: {dataset_id}")
        record = self.records[canonical_id]
        return ResolvedDataset(
            record=record,
            source=SourceSpec(record.source.name, record.source.args, record.source.kwargs),
            origin=self.origins[canonical_id],
            replaced_origins=self.replaced_origins.get(canonical_id, ()),
        )
