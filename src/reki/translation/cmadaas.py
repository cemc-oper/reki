"""Finite service role rules and immutable call association.

No production interface contract is registered here. Real contract/product evidence
must precede registration; synthetic contracts in tests do not prove MUSIC service
availability, request uniqueness or completeness for a business product.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from collections.abc import Mapping

from cedarkit_query import (
    QueryError,
    SourceError,
    normalize_query,
    normalize_statistics,
)
from cedarkit_query.normalize import (
    time_seconds,
    time_text,
    duration_seconds,
    duration_text,
)
from reki.catalog.model import freeze, thaw
from reki.selection.core import matches
from .common import metadata_error, unsupported


@dataclass(frozen=True)
class InterfaceContract:
    id: str
    version: int
    interface_id: str
    method: str
    request_roles: Mapping
    response_roles: Mapping
    level_key_kind: str
    member_numbering: str | None = None

    # This initial finite transport contract verifies a single echoed grid.
    # It is not assigned to an actual service without independent proof.
    def __post_init__(self):
        object.__setattr__(self, "request_roles", freeze(self.request_roles))
        object.__setattr__(self, "response_roles", freeze(self.response_roles))

    @property
    def reference(self):
        return {"id": self.id, "version": self.version}


@dataclass(frozen=True)
class CallRecord:
    request_index: int
    contract: InterfaceContract
    parameters: Mapping
    response: object
    verified: bool

    def __post_init__(self):
        object.__setattr__(self, "parameters", freeze(self.parameters))


def associate(contract, parameters, response, *, request_index):
    # response is the exact object returned by this immutable invocation, not attrs
    # reconstructed from a downstream DataArray. Either an actual raw invocation
    # or this controlled wrapper echo is verified, under an explicit single-field contract.
    if not isinstance(response, Mapping):
        metadata_error(
            "missing_native_metadata",
            "service response has no contracted metadata wrapper",
            request_index=request_index,
        )
    if response.get("truncated"):
        raise SourceError(
            "incomplete_response",
            "",
            "service response was explicitly truncated",
            {"reason": "response_truncated", "request_index": request_index},
        )
    if (
        type(response.get("record_count")) is not int
        or response.get("record_count") != 1
        or response.get("response_kind") != "RetGridArray2D"
    ):
        metadata_error(
            "unsupported_native_encoding",
            "response does not have the contracted single-grid shape",
            request_index=request_index,
        )
    validate_call_parameters(parameters)
    invocation = response.get("invocation")
    if invocation is not None:
        from .nuwe_transport import NuweInvocation

        if not isinstance(invocation, NuweInvocation) or (
            invocation.interface_id != contract.interface_id
            or invocation.method != contract.method
            or invocation.response is not response.get("raw_response")
            or dict(invocation.parameters) != dict(parameters)
            or any(
                type(invocation.parameters.get(k)) is not type(v)
                for k, v in parameters.items()
            )
        ):
            metadata_error(
                "inconsistent_native_metadata",
                "raw response is not bound to this exact client invocation",
                request_index=request_index,
            )
    else:
        echo = response.get("request_parameters")
        if not isinstance(echo, Mapping) or any(
            type(echo.get(k)) is not type(v) or echo.get(k) != v
            for k, v in parameters.items()
        ):
            metadata_error(
                "inconsistent_native_metadata",
                "response cannot be associated with the actual business request",
                request_index=request_index,
            )
    return CallRecord(request_index, contract, parameters, response, True)


def validate_call_parameters(parameters):
    if any(
        k.lower()
        in {
            "password",
            "passwd",
            "pwd",
            "token",
            "authorization",
            "user",
            "userid",
            "signature",
            "sign",
            "url",
        }
        for k in parameters
    ):
        raise QueryError(
            "invalid_config",
            "/source",
            "authentication must stay outside business call records",
        )


def role(record, name, *, optional=False):
    if not record.verified:
        metadata_error(
            "inconsistent_native_metadata",
            "unverified call cannot supply request-association facts",
            request_index=record.request_index,
        )
    response_field = record.contract.response_roles.get(name)
    request_field = record.contract.request_roles.get(name)
    payload = record.response.get("metadata", {})
    present = response_field is not None and response_field in payload
    requested = request_field is not None and request_field in record.parameters
    if (
        present
        and requested
        and (
            type(payload[response_field]) is not type(record.parameters[request_field])
            or payload[response_field] != record.parameters[request_field]
        )
    ):
        metadata_error(
            "inconsistent_native_metadata",
            "response and associated request roles conflict",
            request_index=record.request_index,
            fields={response_field: payload[response_field]},
        )
    if present:
        return payload[response_field], "response"
    if requested:
        return record.parameters[request_field], "request_association"
    if optional:
        return None, None
    metadata_error(
        "missing_native_metadata",
        "contracted native role is absent",
        missing_fields=[name],
        request_index=record.request_index,
    )


def vertical_table(record, table):
    kind = table["key_kind"]
    if kind != record.contract.level_key_kind:
        raise QueryError(
            "invalid_config",
            "/tables",
            "table key kind differs from its interface contract",
            {"reason": "rule_not_applicable"},
        )
    names = ("code",) if kind == "code" else ("level_type", "level")
    native = {}
    origins = {}
    for name in names:
        native[name], origins[name] = role(record, name)
        if kind == "level_type_and_level" and not isinstance(native[name], str):
            metadata_error(
                "invalid_vertical_metadata",
                "joint native layer keys must preserve their string encoding",
            )
    selected = [
        r
        for r in table["rows"]
        if all(
            type(r["native"].get(k)) is type(v) and r["native"].get(k) == v
            for k, v in native.items()
        )
    ]
    if not selected:
        metadata_error(
            "unmapped_native_value",
            "native layer key is absent from the effective table",
            fields=native,
            request_index=record.request_index,
        )
    values = [normalize_query(thaw(r["canonical"])).to_dict() for r in selected]
    if any(v != values[0] for v in values):
        raise QueryError(
            "invalid_config",
            "/tables",
            "same native key has contradictory canonical rows",
            {"reason": "conflicting_table_rows"},
        )
    return values[0], {
        "roles": origins,
        "rows": [r["id"] for r in selected],
        "table": table["id"],
    }


def vertical_candidates(query, table):
    keys = {"level_type", "level", "level_unit", "layer"}
    condition = {k: v for k, v in normalize_query(query).to_dict().items() if k in keys}
    return tuple(thaw(r) for r in table["rows"] if matches(r["canonical"], condition))


def _decode_time(text, zone):
    if not isinstance(text, str) or len(text) != 14 or not text.isdigit():
        metadata_error(
            "invalid_time_metadata",
            "service timestamp must use the contracted fourteen-digit form",
        )
    try:
        naive = datetime.strptime(text, "%Y%m%d%H%M%S")
    except ValueError as exc:
        raise SourceError(
            "metadata_interpretation_failed",
            "",
            "invalid service calendar timestamp",
            {"reason": "invalid_time_metadata"},
        ) from exc
    choices = {
        naive.replace(tzinfo=zone, fold=f).astimezone(timezone.utc)
        for f in (0, 1)
        if naive.replace(tzinfo=zone, fold=f)
        .astimezone(timezone.utc)
        .astimezone(zone)
        .replace(tzinfo=None)
        == naive
    }
    if not choices:
        metadata_error("invalid_time_metadata", "service time falls in a timezone gap")
    if len(choices) != 1:
        metadata_error(
            "unsupported_native_encoding",
            "ambiguous service wall time needs an explicit contract path",
        )
    return next(iter(choices)).isoformat().replace("+00:00", "Z")


def time_fields(record, time_zone, *, fixed_step=None):
    if time_zone is None:
        raise QueryError(
            "invalid_config",
            "/source/time_zone",
            "service timezone is missing",
            {"reason": "missing_context"},
        )
    zone = ZoneInfo(time_zone)
    native, origin = role(record, "time")
    time = _decode_time(native, zone)
    step_value, step_origin = role(record, "step", optional=True)
    if step_value is None:
        if fixed_step is None:
            raise QueryError(
                "invalid_config",
                "/context/scope/step",
                "absence of validTime does not establish analysis PT0H",
                {"reason": "missing_context"},
            )
        step = fixed_step
        step_origin = "definition"
    else:
        if not isinstance(step_value, str) or not step_value.isdigit():
            metadata_error(
                "invalid_time_metadata",
                "service forecast hour must retain its non-negative integer text",
            )
        step = duration_text(int(step_value) * 3600)
    identity = normalize_query({"time": time, "step": step}).to_dict()
    return identity, {
        "time": origin,
        "step": step_origin,
        "valid_time": [origin, step_origin],
    }


def encode_time(query, time_zone):
    query = normalize_query(query).to_dict()
    if (
        "time" not in query
        or not isinstance(query["time"], str)
        or "step" not in query
        or not isinstance(query["step"], str)
    ):
        unsupported("this service contract requires a discrete reference time and step")
    seconds = duration_seconds(query["step"])
    if seconds % 3600 or time_seconds(query["time"]) % 1:
        unsupported(
            "service contract cannot represent sub-hour steps or fractional-second times"
        )
    if time_zone is None:
        raise QueryError(
            "invalid_config",
            "/source/time_zone",
            "service timezone is missing",
            {"reason": "missing_context"},
        )
    zone = ZoneInfo(time_zone)
    dt = datetime.fromisoformat(query["time"].replace("Z", "+00:00")).astimezone(zone)
    text = dt.strftime("%Y%m%d%H%M%S")
    if _decode_time(text, zone) != query["time"]:
        unsupported("service timestamp loses the requested reference time")
    return {"time": text, "step": str(int(seconds / 3600))}


def member_field(record, configuration, table=None):
    code, origin = role(record, "member", optional=True)
    if code is None:
        return {}, {}
    rows = []
    if table is not None:
        selected = [
            r
            for r in table["rows"]
            if type(r["native"].get("code")) is type(code)
            and r["native"].get("code") == code
        ]
        if not selected:
            metadata_error(
                "unmapped_native_value",
                "native member code is absent from the member table",
            )
        members = {r["canonical"]["member"] for r in selected}
        if len(members) != 1:
            raise QueryError(
                "invalid_config",
                "/tables",
                "member code has contradictory rows",
                {"reason": "conflicting_table_rows"},
            )
        number = members.pop()
        rows = [r["id"] for r in selected]
    else:
        if record.contract.member_numbering != "canonical":
            raise QueryError(
                "invalid_config",
                "/context",
                "direct native member numbering has no registered contract",
                {"reason": "missing_context"},
            )
        if not isinstance(code, str) or not code.isdigit():
            metadata_error(
                "invalid_member_metadata",
                "canonical service member must be a non-negative integer text",
            )
        number = int(code)
    role_value = configuration.member_role(number)
    return {
        "member": number,
        **({"member_role": role_value} if role_value is not None else {}),
    }, {"member": origin, "rows": rows}


def statistics_fields(record, fixed, identity):
    if not record.verified:
        metadata_error(
            "inconsistent_native_metadata", "statistics cannot use an unverified call"
        )
    if "statistics" not in fixed:
        raise QueryError(
            "invalid_config",
            "/statistics",
            "service statistics have no effective product definition",
            {"reason": "missing_context"},
        )
    stats = thaw(fixed["statistics"])
    stats = normalize_statistics(stats, complete=True)
    if stats["over"] != "time":
        unsupported(
            "ensemble service products need their finite object/population interpretation path"
        )
    actual = record.response.get("statistics")
    if actual is not None and normalize_statistics(actual, complete=True) != stats:
        metadata_error(
            "fixed_definition_mismatch",
            "response statistics contradict the effective product definition",
        )
    interval = None
    if stats["operation"] != "instantaneous":
        end = time_seconds(identity["valid_time"])
        period = stats["period"]
        start = (
            end - duration_seconds(period["duration"])
            if period["kind"] == "trailing"
            else time_seconds(identity["time"])
        )
        if start < time_seconds(identity["time"]):
            metadata_error(
                "fixed_definition_mismatch",
                "fixed statistical window starts before initialization",
            )
        interval = {"start": time_text(start), "end": time_text(end)}
    time_origins = [
        role(record, "time")[1],
        role(record, "step", optional=True)[1] or "definition",
    ]
    return (
        stats,
        interval,
        {
            "statistics": "definition",
            "interval": sorted(set(["definition", *time_origins])) if interval else [],
        },
    )
