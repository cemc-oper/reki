"""Bounded, metadata-only local GRIB location for public grid queries."""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd
import eccodes

from cedarkit_query import DataReference, QueryError, expand_request

from .catalog.query_binding import BindingPlan
from .core.field_metadata import FieldMetadata
from .readers.grib.index import fingerprint_file
from .readers.grib.reader import GribReader
from .diagnostics import record_io_event
from .sources.file_pattern import FilePatternSource
from .sources.local import LocalSource


@dataclass(frozen=True)
class LocatedItem:
    """One requested field with an explicit availability level."""

    field_identity: dict
    verification: str
    reference: DataReference | None = None
    path: str | None = None


@dataclass(frozen=True)
class ListedField:
    """Native metadata tied to the fingerprinted file that contained it."""

    path: str
    fingerprint: dict
    metadata: FieldMetadata


@dataclass(frozen=True)
class AvailabilityReport:
    """Metadata-only result; missing and remote items remain distinguishable."""

    action: str
    items: tuple[LocatedItem, ...]
    fields: tuple[ListedField, ...] = ()

    @property
    def references(self) -> tuple[DataReference, ...]:
        return tuple(item.reference for item in self.items if item.reference is not None)

    @property
    def metadata(self) -> tuple[FieldMetadata, ...]:
        return tuple(item.metadata for item in self.fields)

    @property
    def status(self) -> str:
        states = {item.verification for item in self.items}
        if "remote_unverified" in states:
            return "unknown"
        if "not_found" in states or "path_exists" in states:
            return "partial"
        return "available" if states or self.fields else "unknown"


def _expanded(plan: BindingPlan, action: str, policy: Mapping | None = None):
    if not isinstance(plan, BindingPlan):
        raise TypeError("plan must be a BindingPlan")
    request = {"api_version": "cedarkit.request/v1", "action": action,
               "query": plan.query.to_dict()}
    if policy is not None:
        request["policy"] = dict(policy)
    return expand_request(request).expanded_requests


def _path(plan: BindingPlan, query: dict, *, local_config_dir: Path | None) -> Path:
    locator = plan.binding.to_dict()["locator"]
    start, lead = query.get("reference_time"), query.get("lead_time")
    if start is None or lead is None:
        raise QueryError("unsupported", "/query", "local path resolution requires reference_time and lead_time")
    if pd.Timedelta(lead).total_seconds() % 3600:
        raise QueryError("unsupported", "/query/lead_time", "local file resolution requires whole hours")
    if locator["resolver"] == "file-pattern":
        source = FilePatternSource(locator["root"], locator["pattern"],
                                   start_time=start, forecast_time=lead)
        try:
            result = source.resolve_path().resolve()
            root = FilePatternSource(locator["root"], ".", start_time=start,
                                     forecast_time=lead).resolve_path().resolve()
        except (ValueError, KeyError) as exc:
            raise QueryError("unsupported", "/binding/locator", "file pattern cannot resolve query") from exc
        except PermissionError as exc:
            raise QueryError("permission_denied", "/binding/locator", "cannot resolve file pattern") from exc
        except OSError as exc:
            raise QueryError("provider_error", "/binding/locator", "cannot resolve file pattern") from exc
        if not result.is_relative_to(root):
            raise QueryError("unsupported", "/binding/locator/pattern", "file pattern escapes configured root")
        return result
    if locator["resolver"] == "reki-local":
        if local_config_dir is None:
            raise QueryError("unsupported", "/binding/locator/config_version",
                             "local config directory must be supplied explicitly")
        try:
            result = LocalSource(locator["data_type"], start_time=pd.Timestamp(start),
                                 forecast_time=pd.Timedelta(lead),
                                 config_dir=local_config_dir).resolve_path()
        except ValueError as exc:
            raise QueryError("unsupported", "/binding/locator", "local configuration cannot resolve query") from exc
        except PermissionError as exc:
            raise QueryError("permission_denied", "/binding/locator", "cannot read local configuration") from exc
        except OSError as exc:
            raise QueryError("provider_error", "/binding/locator", "cannot read local configuration") from exc
        if result is None:
            raise QueryError("not_found", "/resource/locator", "local configuration found no candidate")
        return Path(result).resolve()
    raise QueryError("unsupported", "/binding/locator/resolver", "unsupported local resolver")


def _fingerprint(path: Path, *, hash_contents: bool = False) -> dict:
    try:
        value = fingerprint_file(path)
    except FileNotFoundError as exc:
        raise QueryError("not_found", "/resource/locator", "local resource is absent") from exc
    except PermissionError as exc:
        raise QueryError("permission_denied", "/resource/locator", "cannot stat local resource") from exc
    except OSError as exc:
        raise QueryError("provider_error", "/resource/locator", "cannot stat local resource") from exc
    result = {"size": value.size, "mtime_ns": value.mtime_ns,
              "device": value.st_dev, "inode": value.st_ino}
    if hash_contents:
        digest = hashlib.sha256()
        try:
            record_io_event("file_open_count")
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1 << 20), b""):
                    digest.update(chunk)
        except PermissionError as exc:
            raise QueryError("permission_denied", "/resource/locator", "cannot hash local resource") from exc
        except OSError as exc:
            raise QueryError("provider_error", "/resource/locator", "cannot hash local resource") from exc
        if result != _fingerprint(path):
            raise QueryError("stale_reference", "/resource/fingerprint", "resource changed while hashing")
        result["sha256"] = digest.hexdigest()
    return result


def _resource(path: Path, fingerprint: dict) -> dict:
    return {"kind": "local", "locator": str(path), "fingerprint": fingerprint}


def _reference(plan: BindingPlan, identity: dict, resource: dict, status: str,
               metadata: FieldMetadata | None = None) -> DataReference:
    source = {"api_version": "cedarkit.data-reference/v1", "dataset": plan.query.dataset,
              "field_identity": identity, "binding_id": plan.binding_id,
              "resource": resource, "verification": status,
              "catalog_version": plan.catalog_version}
    if status == "field_confirmed":
        source["field_locator"] = {"field_index": metadata.index, "offset": metadata.offset}
    return DataReference(source)


def _matches(query: dict, metadata: FieldMetadata, native_parameter: str,
             member_roles: Mapping[str, str] | None) -> bool:
    if metadata.parameter != native_parameter:
        return False
    if metadata.start_time is None or metadata.step is None:
        return False
    start = pd.Timestamp(query["reference_time"]).tz_convert("UTC").tz_localize(None)
    if metadata.start_time != start or metadata.step != pd.Timedelta(query["lead_time"]):
        return False
    vertical = query.get("vertical")
    if vertical:
        if vertical["type"] == "surface":
            if metadata.level_type != "sfc":
                return False
        elif vertical["type"] == "isobaric":
            if metadata.level_type != "pl" or metadata.level is None:
                return False
            if metadata.level * 100 != vertical["values"]:
                return False
        elif vertical["type"] == "heightAboveGround":
            if metadata.level_type != "heightAboveGround" or metadata.level != vertical["values"]:
                return False
        else:
            raise QueryError("unsupported", "/query/vertical/type", "vertical type has no GRIB locator mapping")
    statistic = query.get("statistic")
    if statistic:
        if metadata.step_type != statistic["kind"]:
            return False
        if statistic["kind"] != "instant" and metadata.time_range != pd.Timedelta(statistic["window"]):
            return False
    member = query.get("member")
    if member:
        if member_roles is None or member_roles.get(member["id"]) != member["role"]:
            raise QueryError("unsupported", "/query/member", "member role needs an explicit dataset mapping")
        if metadata.member is None or str(metadata.member) != member["id"]:
            return False
    return True


def _check_query(query: dict) -> None:
    if "native_grid" in query or "coverage" in query:
        raise QueryError("unsupported", "/query", "native grid and coverage filtering need verified grid metadata")
    if "vertical" in query and query["vertical"]["type"] not in {"surface", "isobaric", "heightAboveGround"}:
        raise QueryError("unsupported", "/query/vertical/type", "vertical type has no GRIB locator mapping")
    if "vertical" in query and "bounds" in query["vertical"]:
        raise QueryError("unsupported", "/query/vertical/bounds", "layer bounds need a verified mapping")


def locate_fields(plan: BindingPlan, *, native_parameters: Mapping[str, str] | None = None,
                  member_roles: Mapping[str, str] | None = None,
                  local_config_dir: Path | None = None, index_dir: Path | None = None,
                  index_policy: str = "auto", missing: str = "error",
                  hash_resources: bool = False,
                  candidate_paths: Iterable[str | Path] | None = None) -> AvailabilityReport:
    """Locate finite field combinations without decoding values or visiting remote services."""
    if missing not in {"error", "partial"}:
        raise ValueError("missing must be 'error' or 'partial'")
    requests = _expanded(plan, "locate")
    if plan.binding.kind == "cmadaas":
        items = tuple(LocatedItem({key: value for key, value in request.query.to_dict().items()
                                   if key not in {"api_version", "domain", "dataset"}}, "remote_unverified",
                     _reference(plan, {key: value for key, value in request.query.to_dict().items()
                                       if key not in {"api_version", "domain", "dataset"}},
                                {"kind": "cmadaas", "locator": plan.binding.data_code},
                                "remote_unverified")) for request in requests)
        return AvailabilityReport("locate", items)
    explicit_paths = None if candidate_paths is None else tuple(sorted({Path(path).resolve()
                                                                       for path in candidate_paths}))
    if explicit_paths is not None:
        if not explicit_paths:
            raise QueryError("not_found", "/resource/locator", "candidate collection is empty")
        locator = plan.binding.to_dict()["locator"]
        for request in requests:
            query = request.query.to_dict()
            if query.get("reference_time") is None or query.get("lead_time") is None:
                raise QueryError("unsupported", "/query", "local path resolution requires reference_time and lead_time")
            if locator["resolver"] == "file-pattern":
                root = FilePatternSource(locator["root"], ".", start_time=query["reference_time"],
                                         forecast_time=query["lead_time"]).resolve_path().resolve()
            elif locator["resolver"] == "reki-local":
                root = _path(plan, query, local_config_dir=local_config_dir).parent
            else:
                raise QueryError("unsupported", "/binding/locator/resolver", "unsupported local resolver")
            if any(not path.is_relative_to(root) for path in explicit_paths):
                raise QueryError("unsupported", "/resource/locator", "candidate path escapes configured root")
    cache: dict[Path, tuple[dict | None, tuple[FieldMetadata, ...]]] = {}
    items = []
    for request in requests:
        query = request.query.to_dict()
        _check_query(query)
        parameter = query["parameter"]
        if native_parameters is None or parameter not in native_parameters:
            raise QueryError("unsupported", "/query/parameter", "native GRIB parameter needs an explicit mapping")
        paths = explicit_paths if explicit_paths is not None else (_path(plan, query, local_config_dir=local_config_dir),)
        for path in paths:
            if path in cache:
                continue
            try:
                before = _fingerprint(path, hash_contents=hash_resources)
            except QueryError as exc:
                if exc.code == "not_found":
                    cache[path] = (None, ())
                else:
                    raise
            else:
                try:
                    fields = tuple(field.metadata for field in GribReader(
                        None, path, index_policy=index_policy, index_dir=index_dir).all())
                except PermissionError as exc:
                    raise QueryError("permission_denied", "/resource/locator", "cannot read local resource") from exc
                except OSError as exc:
                    raise QueryError("provider_error", "/resource/locator", "cannot scan local resource") from exc
                except (eccodes.CodesInternalError, ValueError) as exc:
                    raise QueryError("provider_error", "/resource/locator", "cannot parse local GRIB headers") from exc
                try:
                    after = _fingerprint(path, hash_contents=hash_resources)
                except QueryError as exc:
                    if exc.code == "not_found":
                        raise QueryError("stale_reference", "/resource/fingerprint",
                                         "resource disappeared during scan") from exc
                    raise
                if before != after:
                    raise QueryError("stale_reference", "/resource/fingerprint", "resource changed during scan")
                cache[path] = (before, fields)
        identity = {key: value for key, value in query.items()
                    if key not in {"api_version", "domain", "dataset"}}
        matches = [(path, fingerprint, field) for path in paths
                   for fingerprint, fields in (cache[path],) if fingerprint is not None
                   for field in fields if _matches(query, field, native_parameters[parameter], member_roles)]
        if len(matches) > 1:
            raise QueryError("multiple_matches", "/query", "multiple GRIB fields match one expanded query")
        absent_path = next((path for path in paths if cache[path][0] is None), None)
        if explicit_paths is not None and absent_path is not None:
            item = LocatedItem(identity, "not_found", path=str(absent_path))
        elif matches:
            path, fingerprint, field = matches[0]
            item = LocatedItem(identity, "field_confirmed", _reference(plan, identity,
                               _resource(path, fingerprint), "field_confirmed", field), str(path))
        else:
            path = next((path for path in paths if cache[path][0] is not None), paths[0])
            fingerprint, _ = cache[path]
            item = (LocatedItem(identity, "not_found", path=str(path)) if fingerprint is None else
                    LocatedItem(identity, "path_exists", _reference(plan, identity,
                                _resource(path, fingerprint), "path_exists"), str(path)))
        if missing == "error" and item.verification in {"not_found", "path_exists"}:
            raise QueryError("not_found", "/query", "requested field was not confirmed",
                             {"verification": item.verification})
        items.append(item)
    for path, (fingerprint, _) in cache.items():
        if fingerprint is not None:
            try:
                current = _fingerprint(path, hash_contents=hash_resources)
            except QueryError as exc:
                if exc.code == "not_found":
                    raise QueryError("stale_reference", "/resource/fingerprint",
                                     "resource disappeared during location") from exc
                raise
            if current != fingerprint:
                raise QueryError("stale_reference", "/resource/fingerprint",
                                 "resource changed during location")
    return AvailabilityReport("locate", tuple(items))


def list_fields(plan: BindingPlan, *, local_config_dir: Path | None = None,
                index_dir: Path | None = None, index_policy: str = "auto") -> AvailabilityReport:
    """List native metadata for finite local candidates; remote status remains unknown."""
    requests = _expanded(plan, "list")
    if plan.binding.kind == "cmadaas":
        return AvailabilityReport("list", tuple(LocatedItem({}, "remote_unverified") for _ in requests))
    paths = set()
    for request in requests:
        query = request.query.to_dict()
        _check_query(query)
        paths.add(_path(plan, query, local_config_dir=local_config_dir))
    fields = []
    for path in sorted(paths):
        try:
            before = _fingerprint(path)
            fields.extend(ListedField(str(path), before, field.metadata) for field in GribReader(
                None, path, index_policy=index_policy, index_dir=index_dir).all())
            if before != _fingerprint(path):
                raise QueryError("stale_reference", "/resource/fingerprint", "resource changed during scan")
        except QueryError:
            raise
        except PermissionError as exc:
            raise QueryError("permission_denied", "/resource/locator", "cannot read local resource") from exc
        except OSError as exc:
            raise QueryError("provider_error", "/resource/locator", "cannot scan local resource") from exc
        except (eccodes.CodesInternalError, ValueError) as exc:
            raise QueryError("provider_error", "/resource/locator", "cannot parse local GRIB headers") from exc
    return AvailabilityReport("list", (), tuple(fields))


def verify_data_reference(value: DataReference | Mapping | str) -> DataReference:
    """Deserialize and reject changed local resources before an offset is reused."""
    try:
        source = json.loads(value) if isinstance(value, str) else value
    except json.JSONDecodeError as exc:
        raise QueryError("invalid_query", "", "data reference is not valid JSON") from exc
    reference = source if isinstance(source, DataReference) else DataReference(source)
    resource = reference.to_dict()["resource"]
    if resource["kind"] == "cmadaas":
        raise QueryError("availability_unknown", "/resource/version", "remote reference is unverified")
    path = Path(resource["locator"])
    try:
        current = _fingerprint(path, hash_contents="sha256" in resource["fingerprint"])
    except QueryError as exc:
        if exc.code == "not_found":
            raise QueryError("stale_reference", "/resource/fingerprint", "local resource is absent") from exc
        raise
    if any(current[key] != resource["fingerprint"][key] for key in current):
        raise QueryError("stale_reference", "/resource/fingerprint", "local resource changed")
    return reference
