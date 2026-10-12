"""Read a finite, explicitly supplied collection of local GRIB resources."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

import eccodes
import numpy as np
import pandas as pd
import xarray as xr

from cedarkit_query import DataReference, QueryError

from .catalog.query_binding import BindingPlan
from .query_locator import (
    _check_query, _expanded, _fingerprint, _matches, _path, _reference, _resource,
)
from .readers.grib.reader import GribReader
from .readers.grib.eccodes._decode import load_message_at_offset
from .readers.grib.eccodes._xarray import create_data_array_from_message
from .sources.file_pattern import FilePatternSource


@dataclass(frozen=True)
class CollectionField:
    """One decoded field, paired with its public identity and source reference."""

    identity: dict
    data: xr.DataArray
    reference: DataReference


@dataclass(frozen=True)
class CollectionResult:
    """Complete cube, or individual fields and an explicit missing report."""

    data: xr.DataArray | None
    fields: tuple[CollectionField, ...]
    expected: tuple[dict, ...]
    missing: tuple[dict, ...]
    missing_paths: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.missing and not self.missing_paths


@dataclass(frozen=True)
class CollectionRequest:
    """One read job for :meth:`CollectionSession.read_many`."""

    plan: BindingPlan
    candidate_paths: tuple[str | Path, ...]
    native_parameters: Mapping[str, str]
    member_roles: Mapping[str, str] | None = None
    missing: str = "error"
    local_config_dir: Path | None = None


@dataclass(frozen=True)
class CollectionCacheInfo:
    resources: int
    metadata_fields: int
    value_bytes: int
    metadata_hits: int
    metadata_misses: int
    value_hits: int
    value_misses: int
    evictions: int
    closed: bool


@dataclass
class _CachedResource:
    fields: tuple
    decoded: dict[int, xr.DataArray]
    value_bytes: int = 0


class CollectionSession:
    """Bounded, caller-owned LRU of native GRIB metadata and decoded fields.

    Query results and transforms are never cached. File fingerprints are checked
    on every read; returned arrays are independent copies and survive close().
    """

    def __init__(self, *, max_resources: int = 32, max_fields: int = 4096,
                 max_bytes: int = 128 << 20, index_dir: Path | None = None,
                 index_policy: str = "auto", hash_resources: bool = False):
        if min(max_resources, max_fields, max_bytes) <= 0:
            raise ValueError("cache limits must be positive")
        self.max_resources = max_resources
        self.max_fields = max_fields
        self.max_bytes = max_bytes
        self.index_dir = index_dir
        self.index_policy = index_policy
        self.hash_resources = hash_resources
        self._entries: OrderedDict[tuple, _CachedResource] = OrderedDict()
        self._hits = [0, 0]
        self._misses = [0, 0]
        self._evictions = 0
        self._closed = False

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError("collection session is closed")

    def _key(self, path: Path, fingerprint: dict) -> tuple:
        return (str(path), tuple(sorted(fingerprint.items())), self.index_policy,
                str(self.index_dir.resolve()) if self.index_dir is not None else None)

    def _trim(self) -> None:
        def totals():
            return (sum(len(entry.fields) for entry in self._entries.values()),
                    sum(entry.value_bytes for entry in self._entries.values()))

        fields, value_bytes = totals()
        while self._entries and (len(self._entries) > self.max_resources or
                                 fields > self.max_fields or value_bytes > self.max_bytes):
            _, entry = self._entries.popitem(last=False)
            fields -= len(entry.fields)
            value_bytes -= entry.value_bytes
            self._evictions += 1

    def _fields(self, path: Path, fingerprint: dict) -> tuple | None:
        self._require_open()
        key = self._key(path, fingerprint)
        entry = self._entries.get(key)
        if entry is None:
            self._misses[0] += 1
            for old_key in tuple(self._entries):
                if old_key[0] == str(path) and old_key != key:
                    del self._entries[old_key]
                    self._evictions += 1
            return None
        self._hits[0] += 1
        self._entries.move_to_end(key)
        return entry.fields

    def _store_fields(self, path: Path, fingerprint: dict, fields: tuple) -> None:
        self._require_open()
        if len(fields) > self.max_fields:
            return
        key = self._key(path, fingerprint)
        self._entries[key] = _CachedResource(fields, {})
        self._entries.move_to_end(key)
        self._trim()

    def _value(self, path: Path, fingerprint: dict, offset: int) -> xr.DataArray | None:
        self._require_open()
        key = self._key(path, fingerprint)
        entry = self._entries.get(key)
        data = None if entry is None else entry.decoded.get(offset)
        if data is None:
            self._misses[1] += 1
            return None
        self._hits[1] += 1
        self._entries.move_to_end(key)
        return data.copy(deep=True)

    def _store_value(self, path: Path, fingerprint: dict, offset: int, data: xr.DataArray) -> None:
        self._require_open()
        key = self._key(path, fingerprint)
        entry = self._entries.get(key)
        size = data.nbytes
        if entry is None or size > self.max_bytes or offset in entry.decoded:
            return
        entry.decoded[offset] = data.copy(deep=True)
        entry.value_bytes += size
        self._entries.move_to_end(key)
        self._trim()

    def cache_info(self) -> CollectionCacheInfo:
        return CollectionCacheInfo(len(self._entries),
                                   sum(len(entry.fields) for entry in self._entries.values()),
                                   sum(entry.value_bytes for entry in self._entries.values()),
                                   self._hits[0], self._misses[0], self._hits[1], self._misses[1],
                                   self._evictions, self._closed)

    def clear(self) -> None:
        self._require_open()
        self._entries.clear()

    def close(self) -> None:
        self._entries.clear()
        self._closed = True

    def __enter__(self) -> CollectionSession:
        self._require_open()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def read(self, plan: BindingPlan, *, candidate_paths: Iterable[str | Path],
             native_parameters: Mapping[str, str], member_roles: Mapping[str, str] | None = None,
             missing: str = "error", local_config_dir: Path | None = None) -> CollectionResult:
        self._require_open()
        return read_grib_collection(plan, candidate_paths=candidate_paths,
                                    native_parameters=native_parameters, member_roles=member_roles,
                                    missing=missing, local_config_dir=local_config_dir,
                                    index_dir=self.index_dir, index_policy=self.index_policy,
                                    hash_resources=self.hash_resources, _session=self)

    def read_many(self, requests: Iterable[CollectionRequest]) -> tuple[CollectionResult, ...]:
        """Execute ordered jobs with shared raw-field reuse; first error raises."""
        self._require_open()
        return tuple(self.read(job.plan, candidate_paths=job.candidate_paths,
                               native_parameters=job.native_parameters,
                               member_roles=job.member_roles, missing=job.missing,
                               local_config_dir=job.local_config_dir) for job in requests)


def _identity(query: dict) -> dict:
    return {key: value for key, value in query.items()
            if key not in {"api_version", "domain", "dataset"}}


def _validate_compatibility(fields: tuple[CollectionField, ...]) -> None:
    first = fields[0].data
    queries = [field.identity for field in fields]
    starts = {query["reference_time"] for query in queries}
    parameters = {query["parameter"] for query in queries}
    statistics = {str(query.get("statistic")) for query in queries}
    vertical_types = {query.get("vertical", {}).get("type") for query in queries}
    if len(starts) != 1 or len(parameters) != 1 or len(statistics) != 1 or len(vertical_types) != 1:
        raise QueryError("unsupported", "/query", "collection requires one parameter, cycle, statistic, and vertical type")
    grid = (first.attrs.get("GRIB_gridType"), first.dims, tuple(first.coords["latitude"].values),
            tuple(first.coords["longitude"].values))
    units = first.attrs.get("units")
    if units is None:
        raise QueryError("unsupported", "/query/parameter", "GRIB parameter unit is unavailable")
    for field in fields:
        data = field.data
        if (data.attrs.get("GRIB_gridType"), data.dims, tuple(data.coords["latitude"].values),
                tuple(data.coords["longitude"].values)) != grid:
            raise QueryError("incompatible_grid", "/query", "GRIB fields have different native grids",
                             {"field_identity": field.identity})
        if data.attrs.get("units") != units:
            raise QueryError("incompatible_units", "/query", "GRIB fields have different native units",
                             {"field_identity": field.identity})


def _cube(fields: tuple[CollectionField, ...]) -> xr.DataArray:
    first = fields[0].data
    queries = [field.identity for field in fields]
    starts = {query["reference_time"] for query in queries}
    parameters = {query["parameter"] for query in queries}
    vertical_types = {query.get("vertical", {}).get("type") for query in queries}

    leads = sorted({pd.Timedelta(query["lead_time"]) for query in queries})
    vertical_type = next(iter(vertical_types))
    has_level = vertical_type in {"isobaric", "heightAboveGround"}
    levels = sorted({query["vertical"]["values"] for query in queries}) if has_level else [None]
    members = sorted({(query["member"]["id"], query["member"]["role"])
                      for query in queries if "member" in query})
    if members and any("member" not in query for query in queries):
        raise QueryError("unsupported", "/query/member", "mixed member and non-member fields")
    if not members:
        members = [(None, None)]
    lookup = {}
    for field in fields:
        query = field.identity
        key = (pd.Timedelta(query["lead_time"]),
               query["vertical"]["values"] if has_level else None,
               query.get("member", {}).get("id"))
        lookup[key] = field
    values = np.stack([lookup[(lead, level, member)].data.values
                       for lead in leads for level in levels for member, _ in members])
    values = values.reshape((len(leads), len(levels), len(members)) + first.shape)
    dimensions = ["lead_time"]
    coordinates = {"lead_time": pd.to_timedelta(leads).to_numpy(),
                   "time": pd.Timestamp(next(iter(starts))).tz_localize(None).to_datetime64(),
                   "valid_time": ("lead_time", [pd.Timestamp(next(iter(starts))).tz_localize(None) + lead
                                                for lead in leads]),
                   "latitude": first.coords["latitude"], "longitude": first.coords["longitude"]}
    if has_level:
        level_name = "isobaricInPa" if vertical_type == "isobaric" else "heightAboveGroundInM"
        dimensions.append(level_name)
        coordinates[level_name] = levels
    else:
        values = values[:, 0]
    if members[0][0] is not None:
        dimensions.append("member")
        coordinates["member"] = [member for member, _ in members]
        coordinates["member_role"] = ("member", [role for _, role in members])
    else:
        values = values[:, :, 0] if has_level else values[:, 0]
    dimensions.extend(first.dims)
    result = xr.DataArray(values, dims=dimensions, coords=coordinates,
                          name=next(iter(parameters)), attrs=dict(first.attrs))
    result.attrs["source_references"] = [field.reference.to_dict() for field in fields]
    return result


def _decode(path: Path, offset: int) -> xr.DataArray:
    message = load_message_at_offset(path, offset)
    if message is None:
        raise ValueError("GRIB field disappeared at its recorded offset")
    try:
        data = create_data_array_from_message(message)
        data.attrs["units"] = eccodes.codes_get(message, "units")
        data.attrs["GRIB_gridType"] = eccodes.codes_get(message, "gridType")
        return data
    finally:
        eccodes.codes_release(message)


def _check_versions(versions: Mapping[Path, dict], *, hash_resources: bool) -> None:
    for path, fingerprint in versions.items():
        try:
            current = _fingerprint(path, hash_contents=hash_resources)
        except QueryError as exc:
            if exc.code == "not_found":
                raise QueryError("stale_reference", "/resource/fingerprint",
                                 "local resource disappeared during read") from exc
            raise
        if current != fingerprint:
            raise QueryError("stale_reference", "/resource/fingerprint",
                             "local resource changed during read")


def read_grib_collection(
    plan: BindingPlan, *, candidate_paths: Iterable[str | Path],
    native_parameters: Mapping[str, str], member_roles: Mapping[str, str] | None = None,
    missing: str = "error", local_config_dir: Path | None = None,
    index_dir: Path | None = None, index_policy: str = "auto",
    hash_resources: bool = False, _session: CollectionSession | None = None,
) -> CollectionResult:
    """Match fields by expanded query identity, then decode and organize them.

    ``candidate_paths`` is an explicit execution snapshot. Each path is scanned
    once regardless of how many fields it contains. Partial results keep decoded
    fields separate and set ``data=None`` rather than silently filling gaps.
    """
    if missing not in {"error", "partial"}:
        raise ValueError("missing must be 'error' or 'partial'")
    if _session is not None:
        _session._require_open()
    if plan.binding.kind != "local":
        raise QueryError("unsupported", "/binding/kind", "collection read requires a local binding")
    requests = _expanded(plan, "read")
    queries = [request.query.to_dict() for request in requests]
    if not queries:
        raise QueryError("invalid_query", "/query", "collection query is empty")
    for query in queries:
        _check_query(query)
        if query["parameter"] not in native_parameters:
            raise QueryError("unsupported", "/query/parameter", "native GRIB parameter needs an explicit mapping")
    if len({query["parameter"] for query in queries}) != 1:
        raise QueryError("unsupported", "/query/parameter", "collection read requires one parameter")
    for query in queries:
        member = query.get("member")
        if member and (member_roles is None or member_roles.get(member["id"]) != member["role"]):
            raise QueryError("unsupported", "/query/member", "member role needs an explicit dataset mapping")
    paths = sorted({Path(path).resolve() for path in candidate_paths})
    if not paths:
        raise QueryError("not_found", "/resource/locator", "candidate collection is empty")
    locator = plan.binding.to_dict()["locator"]
    if locator["resolver"] == "file-pattern":
        try:
            roots = {FilePatternSource(locator["root"], ".",
                                       start_time=query["reference_time"],
                                       forecast_time=query["lead_time"]).resolve_path().resolve()
                     for query in queries}
        except (ValueError, KeyError) as exc:
            raise QueryError("unsupported", "/binding/locator/root", "file pattern root cannot resolve query") from exc
    elif locator["resolver"] == "reki-local":
        roots = {_path(plan, query, local_config_dir=local_config_dir).parent for query in queries}
    else:
        raise QueryError("unsupported", "/binding/locator/resolver", "unsupported local resolver")
    if any(not any(path.is_relative_to(root) for root in roots) for path in paths):
        raise QueryError("unsupported", "/resource/locator", "candidate path escapes configured root")
    candidates = []
    absent_paths = []
    for path in paths:
        try:
            before = _fingerprint(path, hash_contents=hash_resources)
        except QueryError as exc:
            if exc.code != "not_found":
                raise
            absent_paths.append(str(path))
            continue
        try:
            fields = None if _session is None else _session._fields(path, before)
            if fields is None:
                reader = GribReader(None, path, index_policy=index_policy, index_dir=index_dir)
                fields = tuple(reader.all())
        except PermissionError as exc:
            raise QueryError("permission_denied", "/resource/locator", "cannot read local resource") from exc
        except (OSError, ValueError, eccodes.CodesInternalError) as exc:
            raise QueryError("provider_error", "/resource/locator", "cannot scan local GRIB headers") from exc
        if before != _fingerprint(path, hash_contents=hash_resources):
            raise QueryError("stale_reference", "/resource/fingerprint", "resource changed during scan")
        if _session is not None and _session._key(path, before) not in _session._entries:
            _session._store_fields(path, before, fields)
        candidates.extend((path, before, field) for field in fields)

    selected = []
    absent = []
    for query in queries:
        identity = _identity(query)
        matches = [(path, fingerprint, field) for path, fingerprint, field in candidates
                   if _matches(query, field.metadata, native_parameters[query["parameter"]], member_roles)]
        if len(matches) > 1:
            raise QueryError("multiple_matches", "/query", "multiple GRIB fields match one expanded query",
                             {"field_identity": identity, "paths": [str(path) for path, _, _ in matches]})
        if matches:
            selected.append((identity, *matches[0]))
        else:
            absent.append(identity)
    if (absent or absent_paths) and missing == "error":
        raise QueryError("not_found", "/query", "requested fields are missing",
                         {"missing": absent, "missing_paths": absent_paths})

    versions = {path: fingerprint for _, path, fingerprint, _ in selected}
    _check_versions(versions, hash_resources=hash_resources)
    decoded = []
    pending_values = []
    for identity, path, fingerprint, field in selected:
        reference = _reference(plan, identity, _resource(path, fingerprint),
                               "field_confirmed", field.metadata)
        try:
            data = None if _session is None else _session._value(path, fingerprint, field.metadata.offset)
            if data is None:
                data = _decode(path, field.metadata.offset)
                pending_values.append((path, fingerprint, field.metadata.offset, data))
        except (OSError, ValueError, eccodes.CodesInternalError) as exc:
            _check_versions(versions, hash_resources=hash_resources)
            raise QueryError("provider_error", "/resource/locator", "cannot decode GRIB field") from exc
        decoded.append(CollectionField(identity, data, reference))
    _check_versions(versions, hash_resources=hash_resources)
    result_fields = tuple(decoded)
    if result_fields:
        _validate_compatibility(result_fields)
    data = _cube(result_fields) if result_fields and not absent and not absent_paths else None
    if _session is not None:
        for path, fingerprint, offset, value in pending_values:
            _session._store_value(path, fingerprint, offset, value)
    return CollectionResult(data, result_fields, tuple(_identity(query) for query in queries),
                            tuple(absent), tuple(absent_paths))
