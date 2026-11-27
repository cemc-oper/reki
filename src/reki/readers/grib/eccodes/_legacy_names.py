"""Resolve the output names used by the 2026.9.0 GRIB field readers."""

from functools import cache
from importlib.resources import files

import yaml


@cache
def _names_by_key():
    resource = files(__package__).joinpath("legacy-names.yaml")
    entries = yaml.safe_load(resource.read_text(encoding="utf-8"))
    return {tuple(entry["key"]): entry for entry in entries}


def _fixed_surface(attrs, side):
    kind = attrs.get(f"typeOf{side}FixedSurface:int")
    if kind in (None, "undef", "unknown", 255):
        return None, None
    scale = attrs.get(f"scaleFactorOf{side}FixedSurface")
    scaled = attrs.get(f"scaledValueOf{side}FixedSurface")
    if not isinstance(scale, int) or not isinstance(scaled, (int, float)):
        return kind, None
    level = scaled * 10.0 ** -scale
    return kind, level / 100 if kind == 100 else level


def _time_range_hours(attrs):
    unit_hours = {0: 1 / 60, 1: 1, 2: 24, 10: 3, 11: 6, 12: 12, 13: 1 / 3600}
    factor = unit_hours.get(attrs.get("indicatorOfUnitOfTimeRange:int"))
    length = attrs.get("lengthOfTimeRange:int")
    if factor is not None and isinstance(length, int):
        return factor * length
    return None


def output_aliases(attrs):
    key = tuple(attrs.get(name) for name in ("discipline", "parameterCategory", "parameterNumber"))
    entry = _names_by_key().get(key)
    if entry is None:
        return {}

    name = entry["name"]
    variants = entry.get("variants", ())
    if variants:
        first_type, first_level = _fixed_surface(attrs, "First")
        second_type, second_level = _fixed_surface(attrs, "Second")
        actual = {
            "first_level_type": first_type,
            "first_level": first_level,
            "second_level_type": second_type,
            "second_level": second_level,
            "stepType": attrs.get("stepType"),
            "time_range_hours": _time_range_hours(attrs),
        }
        matches = [
            (len(variant["when"]), position, variant["name"])
            for position, variant in enumerate(variants)
            if all(expected is None or expected == actual[field]
                   for field, expected in variant["when"].items())
        ]
        name = max(matches, default=(0, -1, name))[2]

    aliases = {"cemc_name": name}
    if entry.get("wgrib2_name"):
        aliases["wgrib2_name"] = entry["wgrib2_name"]
    return aliases
