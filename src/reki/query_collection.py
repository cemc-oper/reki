"""Read a finite, explicitly supplied collection of local GRIB resources."""

from __future__ import annotations

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
    verify_data_reference,
)
from .readers.grib.reader import GribReader
from .readers.grib.eccodes._decode import load_message_at_offset
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
    levels = sorted({query["vertical"]["values"] for query in queries}) if vertical_type == "isobaric" else [None]
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
               query["vertical"]["values"] if vertical_type == "isobaric" else None,
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
    if vertical_type == "isobaric":
        dimensions.append("isobaricInPa")
        coordinates["isobaricInPa"] = levels
    else:
        values = values[:, 0]
    if members[0][0] is not None:
        dimensions.append("member")
        coordinates["member"] = [member for member, _ in members]
        coordinates["member_role"] = ("member", [role for _, role in members])
    else:
        values = values[:, :, 0] if vertical_type == "isobaric" else values[:, 0]
    dimensions.extend(first.dims)
    result = xr.DataArray(values, dims=dimensions, coords=coordinates,
                          name=next(iter(parameters)), attrs=dict(first.attrs))
    result.attrs["source_references"] = [field.reference.to_dict() for field in fields]
    return result


def read_grib_collection(
    plan: BindingPlan, *, candidate_paths: Iterable[str | Path],
    native_parameters: Mapping[str, str], member_roles: Mapping[str, str] | None = None,
    missing: str = "error", local_config_dir: Path | None = None,
    index_dir: Path | None = None, index_policy: str = "auto",
    hash_resources: bool = False,
) -> CollectionResult:
    """Match fields by expanded query identity, then decode and organize them.

    ``candidate_paths`` is an explicit execution snapshot. Each path is scanned
    once regardless of how many fields it contains. Partial results keep decoded
    fields separate and set ``data=None`` rather than silently filling gaps.
    """
    if missing not in {"error", "partial"}:
        raise ValueError("missing must be 'error' or 'partial'")
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
            reader = GribReader(None, path, index_policy=index_policy, index_dir=index_dir)
            fields = tuple(reader.all())
        except PermissionError as exc:
            raise QueryError("permission_denied", "/resource/locator", "cannot read local resource") from exc
        except (OSError, ValueError, eccodes.CodesInternalError) as exc:
            raise QueryError("provider_error", "/resource/locator", "cannot scan local GRIB headers") from exc
        if before != _fingerprint(path, hash_contents=hash_resources):
            raise QueryError("stale_reference", "/resource/fingerprint", "resource changed during scan")
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

    decoded = []
    for identity, path, fingerprint, field in selected:
        reference = _reference(plan, identity, _resource(path, fingerprint),
                               "field_confirmed", field.metadata)
        verify_data_reference(reference)
        try:
            data = field.to_xarray()
            header = load_message_at_offset(path, field.metadata.offset, headers_only=True)
            if header is None:
                raise ValueError("GRIB field disappeared at its recorded offset")
            try:
                data.attrs["units"] = eccodes.codes_get(header, "units")
                data.attrs["GRIB_gridType"] = eccodes.codes_get(header, "gridType")
            finally:
                eccodes.codes_release(header)
        except (OSError, ValueError, eccodes.CodesInternalError) as exc:
            raise QueryError("provider_error", "/resource/locator", "cannot decode GRIB field") from exc
        verify_data_reference(reference)
        decoded.append(CollectionField(identity, data, reference))
    result_fields = tuple(decoded)
    if result_fields:
        _validate_compatibility(result_fields)
    data = _cube(result_fields) if result_fields and not absent and not absent_paths else None
    return CollectionResult(data, result_fields, tuple(_identity(query) for query in queries),
                            tuple(absent), tuple(absent_paths))
