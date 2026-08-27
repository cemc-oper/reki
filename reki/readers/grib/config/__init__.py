"""Versioned GRIB parameter registry loading and resolution.

The registry is a generated, read-only snapshot. Loading it is lazy so
importing :mod:`reki` never opens YAML files or imports a GRIB backend.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from importlib.resources import files
from types import MappingProxyType
from typing import Any, Mapping, Optional

import pandas as pd
import yaml

from reki.core import FieldQuery
from reki.core.source_spec import _freeze

WHEN_KEYS = ("first_level_type", "first_level", "second_level_type", "second_level", "stepType", "time_range_hours")
_V2 = "reki.parameter-registry/v2"


class ParameterResolutionError(ValueError):
    """Base class for deterministic parameter-resolution failures."""
    code = "parameter_resolution_error"

    def __init__(self, parameter: object, message: str, candidates: tuple[str, ...] = ()):
        self.parameter, self.candidates = parameter, candidates
        super().__init__(message)


class ParameterNotFoundError(ParameterResolutionError):
    code = "parameter_not_found"
    def __init__(self, parameter: object):
        super().__init__(parameter, f"unknown parameter: {parameter!r}")


class ParameterAmbiguityError(ParameterResolutionError):
    code = "parameter_ambiguous"
    def __init__(self, parameter: object, candidates: tuple[str, ...]):
        super().__init__(parameter, f"ambiguous parameter {parameter!r}; candidates: {', '.join(candidates)}", candidates)


class ParameterConditionConflictError(ParameterResolutionError):
    code = "parameter_condition_conflict"
    def __init__(self, parameter: object, condition: str, expected: object, actual: object):
        super().__init__(parameter, f"parameter {parameter!r} fixes {condition}={expected!r}, not {actual!r}")


@dataclass(frozen=True)
class ParameterRecord:
    """Immutable entry or independently queryable variant from the snapshot."""
    parameter_id: str | None
    name: str
    aliases: tuple[str, ...]
    grib_key: Mapping[str, int]
    conditions: Mapping[str, Any] = field(default_factory=dict)
    unit: str | None = None
    external_names: tuple[str, ...] = ()
    is_variant: bool = False
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self):
        if self.parameter_id is not None and not isinstance(self.parameter_id, str):
            raise TypeError("parameter_id must be a string or None")
        if not isinstance(self.name, str) or not self.name:
            raise TypeError("parameter name must be a non-empty string")
        object.__setattr__(self, "aliases", tuple(self.aliases))
        object.__setattr__(self, "external_names", tuple(self.external_names))
        object.__setattr__(self, "grib_key", MappingProxyType(dict(self.grib_key)))
        object.__setattr__(self, "conditions", MappingProxyType(dict(self.conditions)))
        object.__setattr__(self, "raw", _freeze(self.raw, "parameter record"))


@dataclass(frozen=True)
class ResolvedParameter:
    record: ParameterRecord
    query: FieldQuery
    matched_by: str


@dataclass(frozen=True)
class GribParameterKey:
    discipline: int
    category: int
    number: int
    first_level_type: Optional[int] = None
    first_level: Optional[float] = None
    second_level_type: Optional[int] = None
    second_level: Optional[float] = None
    stepType: Optional[str] = None
    time_range_hours: Optional[float] = None


def check_value(expected_value, actual_value) -> bool:
    return expected_value is None or (actual_value is not None and actual_value != "undef" and expected_value == actual_value)


def _validate_when(when: Mapping[str, Any]) -> None:
    unknown = set(when) - set(WHEN_KEYS)
    if unknown:
        raise ValueError(f"unknown parameter conditions: {', '.join(sorted(unknown))}")
    if "time_range_hours" in when and when["time_range_hours"] <= 0:
        raise ValueError("time_range_hours must be positive")


def _record(entry: Mapping[str, Any], variant: Mapping[str, Any] | None = None) -> ParameterRecord:
    source = variant if variant is not None else entry
    when = dict(source.get("when", {}))
    _validate_when(when)
    conditions = dict(when)
    for key in ("typeOfLevel", "level"):
        if key in source:
            conditions[key] = source[key]
        elif variant is not None and key in entry:
            conditions[key] = entry[key]
    key = entry["key"]
    return ParameterRecord(
        source.get("parameter_id"), source["name"], tuple(source.get("aliases", ())),
        {"discipline": int(key["discipline"]), "parameterCategory": int(key["category"]), "parameterNumber": int(key["number"])},
        conditions, source.get("unit", entry.get("unit")),
        (entry["wgrib2_name"],) if entry.get("wgrib2_name") else (), variant is not None, source,
    )


class ParameterIndex:
    """Validated immutable indexes built once from a snapshot document."""
    def __init__(self, entries: list[Mapping[str, Any]], *, api_version: str | None):
        if api_version is not None and api_version != _V2:
            raise ValueError(f"unsupported parameter registry api_version: {api_version!r}")
        self.entries = tuple(entries)
        self.by_grib_key = MappingProxyType({
            (int(e["key"]["discipline"]), int(e["key"]["category"]), int(e["key"]["number"])): e for e in entries
        })
        if len(self.by_grib_key) != len(entries):
            raise ValueError("duplicate GRIB parameter key")
        records = [_record(e) for e in entries]
        records += [_record(e, v) for e in entries for v in e.get("params", ())]
        self.records = tuple(records)
        self.by_id = self._unique("parameter_id", ((r.parameter_id, r) for r in records if r.parameter_id))
        # The generated inventory deliberately has an entry-level ``*.any``
        # record and a fixed variant with the same display name.  The variant
        # is the historical and more specific name resolution target; any
        # other duplicate remains an import-time ambiguity.
        self.by_name = self._unique("name", ((r.name, r) for r in records), prefer_variant=True)
        self.by_alias = self._unique("alias", ((a, r) for r in records for a in r.aliases))
        # wgrib2 names identify a GRIB triple, not a particular variant.
        self.by_external = self._unique("external name", ((a, r) for r in records if not r.is_variant for a in r.external_names))

    @staticmethod
    def _unique(label: str, pairs, *, prefer_variant: bool = False):
        indexed: dict[str, ParameterRecord] = {}
        for name, record in pairs:
            prior = indexed.get(name)
            if prior is not None and prior != record:
                if prefer_variant and prior.grib_key == record.grib_key and prior.is_variant != record.is_variant:
                    indexed[name] = record if record.is_variant else prior
                    continue
                candidates = tuple(sorted(x for x in (prior.parameter_id, record.parameter_id) if x))
                if candidates:
                    raise ParameterAmbiguityError(name, candidates)
                raise ValueError(f"ambiguous {label}: {name!r}")
            indexed[name] = record
        return MappingProxyType(indexed)

    def resolve_record(self, parameter: str) -> tuple[ParameterRecord, str]:
        for label, index in (("parameter_id", self.by_id), ("name", self.by_name), ("alias", self.by_alias), ("external", self.by_external)):
            record = index.get(parameter)
            if record is not None:
                return record, label
        raise ParameterNotFoundError(parameter)

    def reverse(self, param_key: GribParameterKey) -> ParameterRecord | None:
        entry = self.by_grib_key.get((param_key.discipline, param_key.category, param_key.number))
        if entry is None:
            return None
        candidates = [(len(v.get("when", {})), pos, _record(entry, v)) for pos, v in enumerate(entry.get("params", ())) if _variant_matches(v.get("when", {}), param_key)]
        return max(candidates, default=(0, 0, _record(entry)), key=lambda x: (x[0], x[1]))[2]


def _load_document(document: object) -> ParameterIndex:
    if isinstance(document, list):
        return ParameterIndex(document, api_version=None)  # explicit v1 compatibility
    if not isinstance(document, Mapping):
        raise TypeError("parameter registry must be a v2 document or a legacy list")
    if "entries" not in document:
        raise ValueError("parameter registry document requires entries")
    return ParameterIndex(document["entries"], api_version=document.get("api_version"))


@cache
def get_parameter_index() -> ParameterIndex:
    ref = files("reki.readers.grib.config").joinpath("param_registry.yaml")
    with ref.open("r", encoding="utf-8") as f:
        return _load_document(yaml.safe_load(f))


def get_param_registry() -> dict[tuple[int, int, int], dict]:
    return dict(get_parameter_index().by_grib_key)


def _variant_matches(when: Mapping[str, Any], param_key: GribParameterKey) -> bool:
    return all(check_value(expected, getattr(param_key, name)) for name, expected in when.items())


def find_short_name(discipline: int, category: int, number: int) -> Optional[str]:
    entry = get_parameter_index().by_grib_key.get((discipline, category, number))
    return None if entry is None else entry["name"]


def find_wgrib2_name(param_key: GribParameterKey) -> Optional[str]:
    entry = get_parameter_index().by_grib_key.get((param_key.discipline, param_key.category, param_key.number))
    return None if entry is None else entry.get("wgrib2_name")


def find_cemc_name(param_key: GribParameterKey) -> Optional[str]:
    record = get_parameter_index().reverse(param_key)
    return None if record is None else record.name


def find_parameter_record(parameter: str) -> Optional[dict]:
    """Legacy reverse lookup with its historical return shape and priority."""
    index = get_parameter_index()
    for source, mapping in (("wgrib2", index.by_external), ("cemc", index.by_name), ("cemc", index.by_alias)):
        record = mapping.get(parameter)
        if record is not None:
            key = record.grib_key
            return {"key": (key["discipline"], key["parameterCategory"], key["parameterNumber"]), "record": dict(record.raw), "source": source}
    return None


def _fixed_query(record: ParameterRecord) -> tuple[dict[str, Any], dict[str, Any]]:
    conditions, values, extra = record.conditions, {"parameter": dict(record.grib_key)}, {}
    if "typeOfLevel" in conditions: values["level_type"] = conditions["typeOfLevel"]
    if "level" in conditions: values["level"] = conditions["level"]
    if "stepType" in conditions: values["step_type"] = conditions["stepType"]
    if "time_range_hours" in conditions: values["time_range"] = pd.Timedelta(hours=conditions["time_range_hours"])
    for old, grib in (("first_level_type", "typeOfFirstFixedSurface"), ("second_level_type", "typeOfSecondFixedSurface"), ("first_level", "first_level"), ("second_level", "second_level")):
        if old in conditions: extra[grib] = conditions[old]
    return values, extra


def _merge_condition(parameter: str, values: dict[str, Any], extra: dict[str, Any], key: str, actual: Any) -> None:
    if actual is None: return
    expected = values.get(key) if key in values else extra.get(key)
    if expected is not None and expected != actual:
        raise ParameterConditionConflictError(parameter, key, expected, actual)
    if key in {"level_type", "level", "step_type", "time_range", "member"}: values[key] = actual
    else: extra[key] = actual


def resolve_parameter(parameter: str, *, level_type=None, level=None, step_type=None, time_range=None, member=None, extra: Mapping[str, Any] | None = None) -> ResolvedParameter:
    """Strictly resolve an ID, name, alias, or external name to ``FieldQuery``."""
    if not isinstance(parameter, str): raise TypeError("parameter must be a string")
    record, matched_by = get_parameter_index().resolve_record(parameter)
    values, fixed_extra = _fixed_query(record)
    for key, actual in (("level_type", level_type), ("level", level), ("step_type", step_type), ("time_range", pd.Timedelta(time_range) if time_range is not None else None), ("member", member)):
        _merge_condition(parameter, values, fixed_extra, key, actual)
    for key, actual in (extra or {}).items():
        key = {"first_level_type": "typeOfFirstFixedSurface", "second_level_type": "typeOfSecondFixedSurface"}.get(key, key)
        _merge_condition(parameter, values, fixed_extra, key, actual)
    return ResolvedParameter(record, FieldQuery(**values, extra=fixed_extra), matched_by)


__all__ = ["GribParameterKey", "ParameterAmbiguityError", "ParameterConditionConflictError", "ParameterIndex", "ParameterNotFoundError", "ParameterRecord", "ParameterResolutionError", "ResolvedParameter", "WHEN_KEYS", "check_value", "find_cemc_name", "find_parameter_record", "find_short_name", "find_wgrib2_name", "get_param_registry", "get_parameter_index", "resolve_parameter"]
