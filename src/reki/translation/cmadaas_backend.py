"""Execute reviewed scalar CMADaaS grid requests through the shared Query source."""

from collections import defaultdict
from collections.abc import Mapping
from datetime import UTC, datetime
from hashlib import sha256
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np
import xarray as xr
from cedarkit_query import Query, QueryError, SourceError, expand_queries
from cedarkit_query.normalize import _contains, duration_seconds, time_seconds

from reki.catalog.model import thaw
from reki.selection.backend import BranchEvent, FieldReference, Plan, is_concrete
from reki.selection.core import key

from .common import metadata_error, software_origin
from .grib_mapping import _conversion, _covered, _unit, expected_cells

_CONTRACTS = {
    "cmadaas.grid-array2d.analysis": (True, False),
    "cmadaas.grid-array2d.forecast": (False, False),
    "cmadaas.grid-array2d.forecast.member": (False, True),
}
_RULES = {
    "vertical": "cmadaas.vertical_table",
    "time": "cmadaas.time_fields",
    "member": "cmadaas.member_field",
    "statistics": "cmadaas.statistics_fields",
    "unit": "common.value_unit",
}
_RECTANGLE = {"minLat", "maxLat", "minLon", "maxLon"}


def _unsupported(message, *, reason="translation_unavailable"):
    raise QueryError("unsupported", "/queries", message, {"reason": reason})


def _contract(configuration):
    if configuration.product is None:
        raise QueryError(
            "invalid_config", "/source/dataset", "service product required"
        )
    sources = [s for s in configuration.product["sources"] if s["kind"] == "cmadaas"]
    if len(sources) != 1:
        raise QueryError(
            "invalid_config", "/source/dataset", "one service source required"
        )
    source = thaw(sources[0])
    contract = source["interface_contract"]
    if contract["version"] != 1 or contract["id"] not in _CONTRACTS:
        _unsupported("CMADaaS interface contract is not registered")
    try:
        zone = ZoneInfo(source["time_zone"])
    except ZoneInfoNotFoundError as exc:
        raise QueryError(
            "invalid_config", "/source", "unregistered service time zone"
        ) from exc
    analysis, members = _CONTRACTS[contract["id"]]
    return source, zone, analysis, members


def _table_vertical(mapping, tables, identity, configuration):
    rule = mapping["native"]["translate"].get("vertical", {})
    table = tables.get(rule.get("config", {}).get("table"))
    if table is None or table["key_kind"] != "level_type_and_level":
        raise QueryError("invalid_config", "/mappings", "joint level table required")
    source = configuration.report_context()["source"]
    if any(
        k in table["applies_to"]
        and not _contains(table["applies_to"][k], source[k], "literal")
        for k in ("dataset", "product", "product_version")
    ) or (
        "time" in table["applies_to"]
        and not _covered(identity, {"time": table["applies_to"]["time"]})
    ):
        _unsupported("joint level table does not apply to this service")
    applicable = [r for r in table["rows"] if _covered(identity, r["canonical"])]
    if len(applicable) != 1:
        _unsupported(
            "joint service level is missing or ambiguous", reason="mapping_coverage_gap"
        )
    return applicable[0]["native"]


def _unit_offset(source, target, pid, data_code, *, index=None):
    water_equivalent = (
        source == "kg/m2"
        and target == "mm"
        and pid in {"cedarkit.rainc.any", "cedarkit.rainnc.any"}
        and data_code == "NAFP_FOR_FTM_GRAPES_GFS_25KM_GLB"
    )
    return (
        0.0 if water_equivalent else _conversion(source, target, pid=pid, index=index)
    )


def _request(
    mapping, tables, identity, configuration, service, zone, analysis, members, index
):
    rules = mapping["native"].get("translate", {})
    required = {"vertical", "time", "statistics", "unit"} | (
        {"member"} if members else set()
    )
    if not required <= rules.keys() or any(
        _RULES.get(k) != r["rule"] for k, r in rules.items()
    ):
        _unsupported("service translation rules are incomplete")
    if rules.get("member", {}).get("config", {}).get("table") is not None:
        _unsupported("this interface contract uses direct member numbers")
    if "native" in identity or "layer" in identity:
        _unsupported("this scalar grid contract accepts reviewed named levels")
    if not {"time", "step"} <= identity.keys() or not is_concrete(identity):
        _unsupported("service requests need scalar reference time and forecast hour")
    seconds = duration_seconds(identity["step"])
    if seconds % 3600 or seconds < 0 or (analysis and seconds != 0):
        _unsupported("service forecast hours must match the interface contract")
    instant = time_seconds(identity["time"])
    if instant % 1:
        _unsupported("service time has whole-second precision")
    if members != ("member" in identity):
        _unsupported("service member must match the interface contract")
    if not members and "member_role" in identity:
        _unsupported("deterministic service has no member role")
    native_level = _table_vertical(mapping, tables, identity, configuration)
    native = mapping["native"]["match"]
    if (
        set(native) - {"fcstEle", *_RECTANGLE}
        or not isinstance(native.get("fcstEle"), str)
        or not native["fcstEle"].strip()
        or (set(native) & _RECTANGLE and not _RECTANGLE <= native.keys())
        or any(not is_concrete(value) for value in native.values())
    ):
        raise QueryError(
            "invalid_config", "/mappings", "invalid scalar service predicate"
        )
    if _RECTANGLE <= native.keys():
        try:
            south, north, west, east = (
                float(native[k]) for k in ("minLat", "maxLat", "minLon", "maxLon")
            )
        except (ValueError, TypeError) as exc:
            raise QueryError(
                "invalid_config", "/mappings", "numeric rectangle required"
            ) from exc
        if not (-90 <= south <= north <= 90 and -180 <= west <= east <= 360):
            raise QueryError("invalid_config", "/mappings", "invalid rectangle bounds")
    definition = configuration.parameters[identity["parameter"]]
    declared_unit = rules["unit"].get("config", {}).get("source_unit")
    if not isinstance(declared_unit, str):
        raise QueryError("invalid_config", "/mappings", "service source unit required")
    _unit_offset(
        _unit(declared_unit),
        _unit(definition["unit"]),
        identity["parameter"],
        service["data_code"],
        index=index,
    )
    stats = definition["fixed_conditions"].get("statistics", {})
    operation = stats.get("operation", "instantaneous")
    if operation != "instantaneous":
        period = stats.get("period", {})
        if (
            analysis
            or operation != "accumulation"
            or stats.get("over") != "time"
            or period.get("kind") != "trailing"
            or duration_seconds(period["duration"]) != seconds
        ):
            _unsupported("service accumulation needs the reviewed complete time window")
    date = datetime.fromtimestamp(int(instant), UTC).astimezone(zone)
    params = {
        "dataCode": service["data_code"],
        "fcstEle": native["fcstEle"],
        "time": date.strftime("%Y%m%d%H%M%S"),
        "levelType": native_level["level_type"],
        "fcstLevel": native_level["level"],
        **{k: native[k] for k in _RECTANGLE if k in native},
    }
    if not analysis:
        params["validTime"] = str(int(seconds // 3600))
    if members:
        params["fcstMember"] = identity["member"]
    suffix = "InRect" if _RECTANGLE <= params.keys() else ""
    interface = ("getNafpAnaEleGrid" if analysis else "getNafpEleGrid") + suffix
    interface += "ByTimeAndLevel"
    if not analysis:
        interface += "AndValidtime"
    if members:
        interface += "AndFcstMember"
    return {"interface_id": interface, **params}


class CmadaasBackend:
    def __init__(self, configuration, *, client=None):
        self.configuration = configuration
        self.service, self.zone, self.analysis, self.members = _contract(configuration)
        self.client, self.owns_client = client, client is None
        self.mappings = {}
        self.tables = {}
        for resource in configuration.mappings:
            if resource.backend == "cmadaas":
                data = resource.to_dict()
                for table in data["tables"]:
                    self.tables[resource.id, table["id"]] = table
                for mapping in data["mappings"]:
                    self.mappings[resource.id, mapping["id"]] = mapping

    def plan(self, queries, configuration):
        translations, expected = [], []
        scope = configuration.report_context()["source"]
        scope = {k: scope[k] for k in ("dataset", "product", "product_version")}
        for qi, query in enumerate(queries):
            if "parameter" not in query.to_dict():
                _unsupported("service query needs a reviewed parameter")
            branches = []
            for row in expand_queries(
                [query],
                max_expansion=configuration.execution_defaults["max_expansion"],
                member_roles=thaw(configuration.member_roles),
                cemc=False,
            ):
                identity = row.to_dict()
                if "member" in identity:
                    role = configuration.member_role(identity["member"])
                    if role is None:
                        _unsupported("service member role is not registered")
                    identity["member_role"] = role
                compatible = []
                for (resource, _), mapping in self.mappings.items():
                    applies = mapping["applies_to"]
                    if (
                        mapping["parameter_id"] == identity.get("parameter")
                        and all(
                            _contains(applies[k], v, "literal")
                            for k, v in scope.items()
                            if k in applies
                        )
                        and _covered(identity, mapping["when"])
                        and any(
                            _covered(identity, p)
                            for p in configuration.product["provides"]
                            if p["parameter"] == identity["parameter"]
                        )
                        and (
                            "time" not in applies
                            or _covered(identity, {"time": applies["time"]})
                        )
                    ):
                        compatible.append((resource, mapping))
                if len(compatible) != 1:
                    _unsupported(
                        "no unique service mapping covers the query",
                        reason="mapping_coverage_gap",
                    )
                resource, mapping = compatible[0]
                tables = {
                    name: table
                    for (owner, name), table in self.tables.items()
                    if owner == resource
                }
                candidate = _request(
                    mapping,
                    tables,
                    identity,
                    configuration,
                    self.service,
                    self.zone,
                    self.analysis,
                    self.members,
                    qi,
                )
                fields = [
                    k
                    for k in (
                        "time",
                        "step",
                        "valid_time",
                        "level_type",
                        "level",
                        "member",
                        "member_role",
                    )
                    if k in identity
                ]
                branches.append(
                    {
                        "index": len(branches),
                        "backend": "cmadaas",
                        "scope": scope,
                        "candidate_filter": candidate,
                        "residual": identity,
                        "basis": [
                            {
                                "kind": "mapping",
                                "resource": {"kind": "mappings", "id": resource},
                                "mapping": mapping["id"],
                            },
                            {
                                "kind": "definition",
                                "resource": {
                                    "kind": "parameters",
                                    "id": next(
                                        r["id"]
                                        for r in configuration.definitions
                                        if r["role"] == "parameter_registry"
                                    ),
                                },
                                "parameter_id": identity["parameter"],
                            },
                            {
                                "kind": "request_association",
                                "contract": self.service["interface_contract"],
                                "fields": fields,
                            },
                            *(
                                {
                                    "kind": "builtin",
                                    "responsibility": duty,
                                    "rule": rule["rule"],
                                }
                                for duty, rule in mapping["native"]["translate"].items()
                            ),
                        ],
                    }
                )
            translations.append(
                {
                    "query_index": qi,
                    "coverage": {
                        "status": "passed",
                        "message": "Reviewed scalar grid contract and product mapping",
                    },
                    "branches": branches,
                    "checks": [
                        {
                            "code": "context_resolved",
                            "status": "passed",
                            "message": "Pinned service source and time zone",
                        },
                        {
                            "code": "request_association_verified",
                            "status": "pending",
                            "message": "Awaiting the response associated with each scalar request",
                        },
                        {
                            "code": "return_metadata_sufficient",
                            "status": "pending",
                            "message": "Awaiting element, unit and grid checks",
                        },
                        {
                            "code": "complete_retrieval_supported",
                            "status": "passed",
                            "message": "Each request returns one complete two-dimensional grid",
                        },
                    ],
                }
            )
            expected.append(expected_cells(query.to_dict(), configuration))
        return Plan(tuple(translations), tuple(expected))

    def start(self, plan):
        if self.client is None:
            try:
                from nuwe_cmadaas.music import get_or_create_client

                self.client = get_or_create_client(
                    self.configuration.source["config"], None
                )
            except (ImportError, OSError, ValueError) as exc:
                raise SourceError(
                    "io_error", "/source/config", "CMADaaS client initialization failed"
                ) from exc
        if not callable(getattr(self.client, "callAPI_to_gridArray2D", None)):
            raise QueryError(
                "invalid_config", "/source", "client needs callAPI_to_gridArray2D"
            )
        return CmadaasScan(self, plan)

    def close(self):
        if self.owns_client and self.client is not None:
            close = getattr(self.client, "close", None)
            self.client = None
            if close is not None:
                close()


def _acquire(client, candidate):
    from requests import RequestException, Timeout

    interface = candidate["interface_id"]
    params = {k: v for k, v in candidate.items() if k != "interface_id"}
    try:
        response = client.callAPI_to_gridArray2D(interface, dict(params))
    except Timeout as exc:
        raise SourceError("timeout", "", "CMADaaS request timed out") from exc
    except (RequestException, OSError) as exc:
        raise SourceError("io_error", "", "CMADaaS transport failed") from exc
    if not getattr(response, "ok", False):
        info = getattr(response, "request", None)
        code = getattr(info, "error_code", None)
        cause = getattr(info, "cause", None)
        classification = {-1004: "authentication_failed", -10003: "decode_failed"}.get(
            code, "service_error"
        )
        if code == -10001:
            classification = (
                "timeout" if isinstance(cause, (Timeout, TimeoutError)) else "io_error"
            )
        raise SourceError(
            classification, "", "CMADaaS service request failed", {"service_code": code}
        ) from cause
    metadata = getattr(response, "metadata", {})
    if not isinstance(metadata, Mapping):
        metadata_error(
            "missing_native_metadata", "request association metadata is absent"
        )
    required = {
        "interface_id": interface,
        "time": params["time"],
        "level_type": params["levelType"],
        "level": params["fcstLevel"],
    }
    if "validTime" in params:
        required["valid_time"] = params["validTime"]
    if "fcstMember" in params:
        required["member"] = params["fcstMember"]
    elif "member" in metadata:
        metadata_error(
            "invalid_member_metadata", "deterministic response carries a member"
        )
    if "validTime" not in params and "valid_time" in metadata:
        required["valid_time"] = "0"
    for response_key, request_key in (
        ("data_code", "dataCode"),
        ("dataCode", "dataCode"),
    ):
        if response_key in metadata:
            required[response_key] = params[request_key]
    for name, value in required.items():
        if name not in metadata:
            metadata_error(
                "missing_native_metadata",
                "request association metadata is absent",
                missing_fields=[name],
            )
        if str(metadata[name]) != str(value):
            metadata_error(
                "inconsistent_native_metadata",
                "response belongs to a different request",
                fields={name: metadata[name]},
            )
    if any(
        type(value) is not int or value < 0
        for value in (response.lat_count, response.lon_count)
    ):
        raise SourceError(
            "decode_failed", "", "grid dimensions must be nonnegative integers"
        )
    size = np.asarray(response.data).size
    count = response.lat_count * response.lon_count
    if size < count:
        raise SourceError(
            "incomplete_response",
            "",
            "grid payload is truncated",
            {"reason": "response_truncated"},
        )
    if count == 0:
        if response.lat_count == response.lon_count == size == 0:
            return None
        metadata_error(
            "inconsistent_native_metadata", "empty grid has inconsistent dimensions"
        )
    if response.user_element_name != params["fcstEle"]:
        metadata_error(
            "inconsistent_native_metadata",
            "response element differs",
            fields={"fcstEle": response.user_element_name},
        )
    try:
        array = response.to_xarray().load().copy(deep=True)
    except (ValueError, TypeError) as exc:
        raise SourceError(
            "decode_failed", "", "CMADaaS grid shape or coordinates are invalid"
        ) from exc
    if not isinstance(array, xr.DataArray) or array.dims != ("latitude", "longitude"):
        raise SourceError("decode_failed", "", "CMADaaS scalar grid required")
    for name in ("latitude", "longitude"):
        values = array[name].values
        if (
            not np.issubdtype(values.dtype, np.number)
            or np.iscomplexobj(values)
            or not np.isfinite(values).all()
            or len(np.unique(values)) != len(values)
        ):
            metadata_error(
                "inconsistent_native_metadata", "grid coordinates are invalid"
            )
    if _RECTANGLE <= params.keys() and not (
        np.all(
            (array.latitude.values >= float(params["minLat"]))
            & (array.latitude.values <= float(params["maxLat"]))
        )
        and np.all(
            (array.longitude.values >= float(params["minLon"]))
            & (array.longitude.values <= float(params["maxLon"]))
        )
    ):
        metadata_error(
            "inconsistent_native_metadata",
            "grid lies outside the requested rectangle",
        )
    if (
        not np.issubdtype(array.dtype, np.number)
        or np.iscomplexobj(array.values)
        or np.isinf(array.values).any()
    ):
        raise SourceError("decode_failed", "", "CMADaaS numeric grid required")
    return array


def _digest(array):
    return sha256(np.ascontiguousarray(array, dtype="<f8")).hexdigest()


class CmadaasScan:
    def __init__(self, backend, plan):
        self.backend, self.plan = backend, plan
        self.context = {
            "origins": {"adapter": software_origin("cmadaas.grid-array2d.v1")}
        }
        self.checks = {}
        self._iterator = None

    def __iter__(self):
        self._iterator = self._fields()
        return self._iterator

    def close(self):
        if self._iterator is not None:
            self._iterator.close()

    def _fields(self):
        grouped = defaultdict(list)
        for translation in self.plan.translations:
            for branch in translation["branches"]:
                grouped[key(branch["candidate_filter"])].append(
                    (translation["query_index"], branch)
                )
        for entries in grouped.values():
            branch = entries[0][1]
            if len({key(b["residual"]) for _, b in entries}) != 1:
                raise QueryError(
                    "invalid_config",
                    "/mappings",
                    "one service request has conflicting business identities",
                )
            links = tuple((qi, b["index"]) for qi, b in entries)
            for qi, bi in links:
                yield BranchEvent(qi, bi, "started")
            array = _acquire(self.backend.client, thaw(branch["candidate_filter"]))
            if array is not None:
                identity = thaw(branch["residual"])
                pid = identity["parameter"]
                resource = branch["basis"][0]
                mapping = self.backend.mappings[
                    resource["resource"]["id"], resource["mapping"]
                ]
                declared = mapping["native"]["translate"]["unit"]["config"][
                    "source_unit"
                ]
                raw_unit = array.attrs.get("units")
                unit = _unit({"kg.m-2": "kg/m2", "gpm": "Gpm"}.get(raw_unit, raw_unit))
                if unit != _unit(declared):
                    metadata_error(
                        "inconsistent_native_metadata",
                        "response unit contradicts the mapping",
                        fields={"units": raw_unit},
                    )
                definition = self.backend.configuration.parameters[pid]
                target = _unit(definition["unit"])
                offset = _unit_offset(
                    unit, target, pid, branch["candidate_filter"]["dataCode"]
                )
                grid = {
                    "type": "cmadaas.latlon",
                    "latitude_sha256": _digest(array.latitude.values),
                    "longitude_sha256": _digest(array.longitude.values),
                }
                source = thaw(branch["candidate_filter"])
                response_sha = sha256(
                    (_digest(array.values) + key(grid)).encode()
                ).hexdigest()
                metadata = {
                    "parameter_id": pid,
                    "parameter_name": definition["name"],
                    "unit": target,
                    "source_unit": unit,
                    "mapping_ids": [mapping["id"]],
                    "response_unit": raw_unit,
                    "source": {"request": source, "response_sha256": response_sha},
                    "vertical_definition": {"id": "cmadaas.levels"},
                }
                if (
                    definition["fixed_conditions"]
                    .get("statistics", {})
                    .get("operation")
                    == "accumulation"
                ):
                    metadata["statistical_interval"] = {
                        "start": identity["time"],
                        "end": identity["valid_time"],
                    }
                values = array + offset if offset else array
                yield FieldReference(
                    "cmadaas:" + sha256(key(source).encode()).hexdigest(),
                    Query(identity),
                    metadata,
                    grid,
                    lambda a=values: a,
                    links,
                )
            for qi, bi in links:
                yield BranchEvent(qi, bi, "exhausted")
        for translation in self.plan.translations:
            self.checks[translation["query_index"]] = [
                {
                    "code": "request_association_verified",
                    "status": "passed",
                    "message": "All returned grids are associated with their exact scalar requests",
                },
                {
                    "code": "return_metadata_sufficient",
                    "status": "passed",
                    "message": "Returned element, unit, dimensions and coordinates were checked",
                },
            ]
