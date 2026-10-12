"""Explicit compatibility conversion from existing reki field selections."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Mapping

import pandas as pd

from cedarkit_query import Query, QueryError

from .core.field_query import FieldQuery
from .readers.grib.config import ParameterResolutionError, resolve_parameter


_LEVEL_TYPES = {
    "sfc": ("surface", None, 1),
    "surface": ("surface", None, 1),
    "pl": ("isobaric", "hPa", 100),
    "isobaricInhPa": ("isobaric", "hPa", 100),
    "isobaricInPa": ("isobaric", "Pa", 100),
    "heightAboveGround": ("heightAboveGround", "m", 103),
    "ml": ("modelLevel", "1", 131),
}


def _time(value: Any) -> str:
    if value is None:
        raise QueryError("invalid_query", "/query/reference_time", "reference_time is required")
    if isinstance(value, str):
        return value
    if isinstance(value, (datetime, pd.Timestamp)):
        time = pd.Timestamp(value)
        if time.tzinfo is None:
            raise QueryError("invalid_query", "/query/reference_time", "timezone is required")
        if time.nanosecond or time.microsecond:
            raise QueryError("invalid_query", "/query/reference_time", "whole-second time is required")
        return time.isoformat()
    raise QueryError("invalid_query", "/query/reference_time", "unsupported reference_time value")


def _seconds(value: Any, path: str, *, positive: bool = False) -> int:
    if isinstance(value, (int, float, bool)):
        raise QueryError("invalid_query", path, "numeric durations need an explicit unit")
    try:
        delta = pd.Timedelta(value)
        nanoseconds = int(delta.value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise QueryError("invalid_query", path, "invalid duration") from exc
    if pd.isna(delta) or nanoseconds % 1_000_000_000 or nanoseconds < 0 or (positive and nanoseconds == 0):
        raise QueryError("invalid_query", path, "duration must be nonnegative whole seconds")
    return nanoseconds // 1_000_000_000


def _lead(value: Any) -> tuple[str, int]:
    if value is None:
        raise QueryError("invalid_query", "/query/lead_time", "lead_time is required")
    seconds = _seconds(value, "/query/lead_time")
    return f"PT{seconds}S", seconds


def _vertical(query: FieldQuery) -> dict[str, Any] | None:
    level_type = query.level_type
    extra_level = query.extra.get("typeOfLevel")
    if level_type is None and extra_level is not None:
        level_type = extra_level
    if level_type is None:
        if query.level is not None:
            raise QueryError("unsupported", "/field_query/level", "level has no explicit level_type")
        return None
    if not isinstance(level_type, str) or level_type not in _LEVEL_TYPES:
        raise QueryError("unsupported", "/field_query/level_type", "level type has no public mapping")
    kind, unit, code = _LEVEL_TYPES[level_type]
    if extra_level is not None and extra_level not in _LEVEL_TYPES:
        raise QueryError("unsupported", "/field_query/extra/typeOfLevel", "unknown native level type")
    if extra_level is not None and _LEVEL_TYPES[extra_level][:2] != (kind, unit):
        raise QueryError("invalid_query", "/field_query/extra/typeOfLevel", "native level type conflicts")
    first_code = query.extra.get("typeOfFirstFixedSurface")
    if first_code is not None and first_code != code:
        raise QueryError("invalid_query", "/field_query/extra/typeOfFirstFixedSurface", "fixed surface conflicts")
    second_code = query.extra.get("typeOfSecondFixedSurface")
    if second_code is not None and second_code != 255:
        raise QueryError("unsupported", "/field_query/extra/typeOfSecondFixedSurface", "layer surface needs bounds mapping")
    if kind == "surface":
        if query.level not in (None, 0):
            raise QueryError("unsupported", "/field_query/level", "surface has no level value")
        return {"type": "surface"}
    if query.level is None:
        raise QueryError("invalid_query", "/field_query/level", "level value is required")
    values = list(query.level) if isinstance(query.level, (tuple, list)) else [query.level]
    if not values or any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in values):
        raise QueryError("unsupported", "/field_query/level", "only numeric level values can be converted")
    return {"type": kind, "unit": unit, "values": values[0] if len(values) == 1 else values}


def query_from_field_query(
    dataset: str,
    field_query: FieldQuery,
    parameter_id: str,
    reference_time: Any,
    lead_time: Any,
    *,
    native_parameter: str | None = None,
    member_roles: Mapping[str, str] | None = None,
) -> Query:
    """Convert only verified old conditions; never discard an unmatched filter.

    ``native_parameter`` asserts an externally verified mapping from the old
    short name to ``parameter_id``. ``member_roles`` gives explicit roles for
    old numeric/member IDs. Neither is inferred from a GRIB code or ID zero.
    """
    if not isinstance(dataset, str) or not dataset or not isinstance(parameter_id, str) or not parameter_id:
        raise QueryError("invalid_query", "/query", "dataset and parameter_id are required")
    if not isinstance(field_query, FieldQuery):
        raise TypeError("field_query must be a FieldQuery")
    if isinstance(field_query.parameter, Mapping):
        try:
            registry_key = resolve_parameter(parameter_id).record.grib_key
        except ParameterResolutionError as exc:
            raise QueryError("unmapped_parameter", "/query/parameter", "stable parameter has no GRIB key mapping") from exc
        if native_parameter is None or dict(field_query.parameter) != dict(registry_key):
            raise QueryError("unsupported", "/field_query/parameter", "native GRIB key has no verified mapping")
    elif field_query.parameter is not None and field_query.parameter not in (parameter_id, native_parameter):
        raise QueryError("unsupported", "/field_query/parameter", "native parameter has no verified mapping")
    allowed_extra = {"step", "typeOfLevel", "typeOfFirstFixedSurface", "typeOfSecondFixedSurface",
                     "first_level"}
    unknown = set(field_query.extra) - allowed_extra
    if unknown:
        raise QueryError("unsupported", "/field_query/extra", f"unmapped native keys: {', '.join(sorted(unknown))}")
    if "first_level" in field_query.extra and field_query.extra["first_level"] != field_query.level:
        raise QueryError("invalid_query", "/field_query/extra/first_level", "native level conflicts")
    lead, lead_seconds = _lead(lead_time)
    if "step" in field_query.extra:
        native_step = field_query.extra["step"]
        if isinstance(native_step, bool):
            raise QueryError("invalid_query", "/field_query/extra/step", "boolean step is not a time")
        step_seconds = _seconds(pd.Timedelta(hours=native_step) if isinstance(native_step, (int, float))
                                else native_step, "/field_query/extra/step")
        if step_seconds != lead_seconds:
            raise QueryError("invalid_query", "/field_query/extra/step", "native step conflicts with lead_time")
    result: dict[str, Any] = {"api_version": "cedarkit.query/v1", "domain": "grid", "dataset": dataset,
                              "parameter": parameter_id, "reference_time": _time(reference_time), "lead_time": lead}
    vertical = _vertical(field_query)
    if vertical is not None:
        result["vertical"] = vertical
    step_type = field_query.step_type
    if step_type is not None:
        if step_type == "instant":
            if field_query.time_range is not None:
                raise QueryError("invalid_query", "/field_query/time_range", "instant cannot have a window")
            result["statistic"] = {"kind": "instant"}
        elif step_type in ("accum", "mean", "min", "max"):
            if field_query.time_range is None:
                raise QueryError("invalid_query", "/field_query/time_range", "statistic requires a window")
            seconds = _seconds(field_query.time_range, "/field_query/time_range", positive=True)
            result["statistic"] = {"kind": step_type, "window": f"PT{seconds}S"}
        else:
            raise QueryError("unsupported", "/field_query/step_type", "statistic kind has no public mapping")
    elif field_query.time_range is not None:
        raise QueryError("unsupported", "/field_query/time_range", "window has no statistic kind")
    if field_query.member is not None:
        members = field_query.member if isinstance(field_query.member, (tuple, list)) else (field_query.member,)
        mapped = []
        for item in members:
            identity = str(item)
            role = None if member_roles is None else member_roles.get(identity)
            if role not in ("control", "perturbation"):
                raise QueryError("unsupported", "/field_query/member", "member role requires an explicit table")
            mapped.append({"id": identity, "role": role})
        result["member"] = mapped[0] if len(mapped) == 1 else mapped
    return Query(result)
