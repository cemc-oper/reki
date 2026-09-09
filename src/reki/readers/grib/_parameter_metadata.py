"""Shared GRIB-header conversion for parameter-registry lookups."""

from __future__ import annotations

import math
from typing import Any, Mapping

from .config import GribParameterKey


_TIME_RANGE_UNIT_HOURS = {
    0: 1 / 60,
    1: 1.0,
    2: 24.0,
    10: 3.0,
    11: 6.0,
    12: 12.0,
    13: 1 / 3600,
}


def _integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _value(attrs: Mapping[str, Any], key: str) -> Any:
    return attrs.get(f"{key}:int", attrs.get(key))


def _scaled_surface_value(surface_type: Any, scale_factor: Any, scaled_value: Any) -> float | None:
    surface_type, scale_factor, scaled_value = (
        _integer(surface_type), _integer(scale_factor), _integer(scaled_value),
    )
    if surface_type is None or scale_factor is None or scaled_value is None:
        return None
    value = math.pow(10, -scale_factor) * scaled_value
    return value / 100 if surface_type == 100 else value


def time_range_hours_from_attrs(attrs: Mapping[str, Any]) -> float | None:
    """Normalize GRIB statistical-window metadata to hours when exact."""
    unit = _integer(_value(attrs, "indicatorOfUnitOfTimeRange"))
    length = _integer(_value(attrs, "lengthOfTimeRange"))
    factor = None if unit is None else _TIME_RANGE_UNIT_HOURS.get(unit)
    return None if length is None or factor is None else factor * length


def attrs_to_grib_parameter_key(attrs: Mapping[str, Any]) -> GribParameterKey | None:
    """Build the registry lookup key used for CEMC and wgrib2 names."""
    discipline = _integer(attrs.get("discipline"))
    category = _integer(attrs.get("parameterCategory"))
    number = _integer(attrs.get("parameterNumber"))
    if discipline is None or category is None or number is None:
        return None

    first_level_type = _integer(_value(attrs, "typeOfFirstFixedSurface"))
    second_level_type = _integer(_value(attrs, "typeOfSecondFixedSurface"))
    first_level = _scaled_surface_value(
        first_level_type, attrs.get("scaleFactorOfFirstFixedSurface"),
        attrs.get("scaledValueOfFirstFixedSurface"),
    )
    second_level = _scaled_surface_value(
        second_level_type, attrs.get("scaleFactorOfSecondFixedSurface"),
        attrs.get("scaledValueOfSecondFixedSurface"),
    )
    if second_level_type == 255:
        second_level_type, second_level = None, None

    return GribParameterKey(
        discipline=discipline, category=category, number=number,
        first_level_type=first_level_type, first_level=first_level,
        second_level_type=second_level_type, second_level=second_level,
        stepType=attrs.get("stepType"), time_range_hours=time_range_hours_from_attrs(attrs),
    )
