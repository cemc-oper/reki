"""Finite MUSIC wire shapes reviewed against the 2026-10-07 portal snapshot.

These declarations validate native request/return shape only. They do not select
a product, register its business contract, prove empty-result semantics, or prove
full retrieval/snapshot consistency. Raw sources and conflicts are indexed by I06.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
import re

from cedarkit_query import QueryError


@dataclass(frozen=True)
class GridWireProfile:
    analysis: bool = False
    member: bool = False
    rectangle: bool = False

    @property
    def roles(self):
        roles = {"time": "time", "level_type": "levelType", "level": "fcstLevel"}
        if not self.analysis:
            roles["step"] = "validTime"
        if self.member:
            roles["member"] = "fcstMember"
        return roles

    @property
    def required(self):
        fields = {"dataCode", "fcstEle", *self.roles.values()}
        if self.rectangle:
            fields.update(("minLat", "maxLat", "minLon", "maxLon"))
        return frozenset(fields)


GRID_WIRE_PROFILES = MappingProxyType(
    {
        "getNafpAnaEleGridByTimeAndLevel": GridWireProfile(analysis=True),
        "getNafpAnaEleGridInRectByTimeAndLevel": GridWireProfile(
            analysis=True, rectangle=True
        ),
        "getNafpEleGridByTimeAndLevelAndValidtime": GridWireProfile(),
        "getNafpEleGridInRectByTimeAndLevelAndValidtime": GridWireProfile(
            rectangle=True
        ),
        "getNafpEleGridByTimeAndLevelAndValidtimeAndFcstMember": GridWireProfile(
            member=True
        ),
        "getNafpEleGridInRectByTimeAndLevelAndValidtimeAndFcstMember": GridWireProfile(
            member=True, rectangle=True
        ),
    }
)


def _invalid(message, **context):
    raise QueryError(
        "invalid_config", "/source/interface_contract", message, context or None
    )


def profile_for(contract):
    profile = GRID_WIRE_PROFILES.get(contract.interface_id)
    if profile is None:
        raise QueryError(
            "unsupported",
            "/source/interface_contract",
            "interface has no reviewed scalar-grid wire profile",
            {"reason": "translation_unavailable"},
        )
    if dict(contract.request_roles) != profile.roles or contract.response_roles:
        _invalid(
            "native identity roles must match the reviewed request shape; raw grid has no response identity axes"
        )
    if contract.level_key_kind != "level_type_and_level":
        _invalid("scalar grid wire requires the complete joint layer key")
    return profile


def validate_parameters(profile, parameters):
    missing, extra = (
        profile.required - parameters.keys(),
        parameters.keys() - profile.required,
    )
    if missing:
        _invalid(
            "scalar-grid identity lacks required request fields",
            missing_fields=sorted(missing),
            reason="missing_context",
        )
    if extra:
        raise QueryError(
            "unsupported",
            "/source/interface_contract",
            "request fields have no interpretation in this finite wire shape",
            {"reason": "translation_unavailable", "native_fields": sorted(extra)},
        )
    for key in ("dataCode", "fcstEle", "levelType", "fcstLevel", "time"):
        value = parameters[key]
        if (
            type(value) is not str
            or not value
            or value != value.strip()
            or any(c in value for c in ",;&=")
        ):
            _invalid("request needs one exact scalar text value", native_field=key)
    stamp = parameters["time"]
    if re.fullmatch(r"[0-9]{14}", stamp) is None:
        _invalid("native time needs fourteen digits", native_field="time")
    try:
        datetime.strptime(stamp, "%Y%m%d%H%M%S")
    except ValueError as exc:
        raise QueryError(
            "invalid_config",
            "/source/interface_contract",
            "native time is not a calendar timestamp",
        ) from exc
    if not profile.analysis:
        step = parameters["validTime"]
        if not (
            (type(step) is int and step >= 0)
            or (type(step) is str and re.fullmatch(r"[0-9]+", step))
        ):
            _invalid(
                "validTime needs one nonnegative integer hour", native_field="validTime"
            )
    if profile.member:
        member = parameters["fcstMember"]
        if not (
            type(member) is int
            or (
                type(member) is str
                and member
                and member == member.strip()
                and not any(c in member for c in ",;&=")
            )
        ):
            _invalid(
                "member needs one native code; numbering remains product-defined",
                native_field="fcstMember",
            )
    if profile.rectangle:
        for key in ("minLat", "maxLat", "minLon", "maxLon"):
            value = parameters[key]
            try:
                if (
                    type(value) not in (int, float, str)
                    or not Decimal(str(value)).is_finite()
                ):
                    raise ValueError
            except (InvalidOperation, ValueError) as exc:
                raise QueryError(
                    "invalid_config",
                    "/source/interface_contract",
                    "rectangle endpoint needs a finite scalar",
                    {"native_field": key},
                ) from exc
            number = Decimal(str(value))
            if number.as_tuple().exponent < -4:
                _invalid(
                    "reviewed rectangle endpoint permits at most four decimal places; no rounding is applied",
                    native_field=key,
                )
            if key in {"minLat", "maxLat"} and not -90 <= number <= 90:
                _invalid(
                    "rectangle latitude is outside the declared -90 to 90 degree range",
                    native_field=key,
                )
