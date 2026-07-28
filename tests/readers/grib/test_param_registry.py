"""
Validation of ``reki/readers/grib/config/param_registry.yaml`` against the
numbered rules of ``param_registry_spec.md`` (v1.1).

- Structural rules (F/E/K/V/C1, C2 部分) are checked with the JSON Schema
  from spec appendix A (kept in sync manually).
- Cross-field and global rules (U1-U4, C2-C4, N2) are pytest assertions
  named after the rule numbers.
- Display rules (L1-L3) emit warnings only.
"""

import re
import warnings
from importlib.resources import files

import pytest
import yaml

pytest.importorskip("jsonschema")
import jsonschema

WHEN_KEYS = {
    "first_level_type",
    "first_level",
    "second_level_type",
    "second_level",
    "stepType",
    "time_range_hours",
}

STEP_TYPE_VALUES = {"instant", "accum", "max", "min", "avg"}

NAME_PATTERN = re.compile(r"^\S+$")

#: JSON Schema, mirror of param_registry_spec.md appendix A (v1.1)
REGISTRY_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["key", "name"],
        "additionalProperties": False,
        "properties": {
            "key": {
                "type": "object",
                "required": ["discipline", "category", "number"],
                "additionalProperties": False,
                "properties": {
                    "discipline": {"type": "integer", "minimum": 0, "maximum": 255},
                    "category": {"type": "integer", "minimum": 0, "maximum": 255},
                    "number": {"type": "integer", "minimum": 0, "maximum": 255},
                },
            },
            "name": {"type": "string", "pattern": r"^\S+$"},
            "aliases": {"type": "array", "items": {"type": "string", "pattern": r"^\S+$"}},
            "wgrib2_name": {"type": "string", "pattern": r"^\S+$"},
            "unit": {"type": "string", "minLength": 1},
            "description": {"type": "string", "minLength": 1},
            "description_cn": {"type": "string", "minLength": 1},
            "typeOfLevel": {"type": "string", "minLength": 1},
            "level": {"type": "number"},
            "params": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name", "when"],
                    "additionalProperties": False,
                    "properties": {
                        "name": {"type": "string", "pattern": r"^\S+$"},
                        "aliases": {"type": "array", "items": {"type": "string", "pattern": r"^\S+$"}},
                        "when": {
                            "type": "object",
                            "minProperties": 1,
                            "additionalProperties": False,
                            "properties": {
                                "first_level_type": {"type": "integer", "minimum": 0, "maximum": 255},
                                "first_level": {"type": "number"},
                                "second_level_type": {"type": "integer", "minimum": 0, "maximum": 255},
                                "second_level": {"type": "number"},
                                "stepType": {"type": "string"},
                                "time_range_hours": {"type": "number", "exclusiveMinimum": 0},
                            },
                        },
                        "typeOfLevel": {"type": "string", "minLength": 1},
                        "level": {"type": "number"},
                        "unit": {"type": "string", "minLength": 1},
                        "description": {"type": "string", "minLength": 1},
                        "description_cn": {"type": "string", "minLength": 1},
                    },
                },
            },
        },
    },
}


def _load_registry() -> list:
    ref = files("reki.readers.grib.config").joinpath("param_registry.yaml")
    with ref.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def registry() -> list:
    return _load_registry()


def _entry_label(entry: dict) -> str:
    key = entry["key"]
    return f"({key['discipline']}, {key['category']}, {key['number']}) {entry['name']}"


def test_schema_structure(registry):
    """Spec appendix A: structural rules F/E/K/V and C1 (when 键白名单)."""
    jsonschema.validate(registry, REGISTRY_SCHEMA)


def test_registry_U1_unique_keys(registry):
    keys = [
        (e["key"]["discipline"], e["key"]["category"], e["key"]["number"])
        for e in registry
    ]
    assert len(keys) == len(set(keys)), (
        f"duplicate keys: {sorted({k for k in keys if keys.count(k) > 1})}"
    )


def test_registry_U2_unique_variant_names(registry):
    for entry in registry:
        names = [v["name"] for v in entry.get("params", [])]
        assert len(names) == len(set(names)), (
            f"{_entry_label(entry)}: duplicate variant names "
            f"{sorted({n for n in names if names.count(n) > 1})}"
        )


def test_registry_U3_generic_named_variant_at_most_once(registry):
    for entry in registry:
        count = sum(1 for v in entry.get("params", []) if v["name"] == entry["name"])
        assert count <= 1, f"{_entry_label(entry)}: {count} variants share the generic name"


def test_registry_U4_aliases_no_conflict(registry):
    all_names = set()
    for entry in registry:
        names = {entry["name"]} | {v["name"] for v in entry.get("params", [])}
        all_names |= names
        aliases = list(entry.get("aliases", []))
        for variant in entry.get("params", []):
            aliases += variant.get("aliases", [])
        conflict = names & set(aliases)
        assert not conflict, f"{_entry_label(entry)}: aliases conflict with names: {conflict}"
    # SHOULD: aliases globally unique against all names
    for entry in registry:
        own_names = {entry["name"]} | {v["name"] for v in entry.get("params", [])}
        for alias in entry.get("aliases", []):
            if alias in all_names - own_names:
                warnings.warn(f"L/U4: alias {alias!r} of {_entry_label(entry)} "
                              f"collides with another entry's name")
        for variant in entry.get("params", []):
            for alias in variant.get("aliases", []):
                if alias in all_names - own_names:
                    warnings.warn(f"L/U4: alias {alias!r} of {_entry_label(entry)} "
                                  f"collides with another entry's name")


def test_registry_C2_second_level_requires_first(registry):
    for entry in registry:
        for variant in entry.get("params", []):
            when = variant["when"]
            has_second = "second_level_type" in when or "second_level" in when
            if has_second:
                assert "first_level_type" in when and "first_level" in when, (
                    f"{_entry_label(entry)}/{variant['name']}: second_level without first_level"
                )
                assert "second_level_type" in when and "second_level" in when, (
                    f"{_entry_label(entry)}/{variant['name']}: second_level_type/second_level must appear in pair"
                )


def test_registry_C3_time_range_hours(registry):
    for entry in registry:
        for variant in entry.get("params", []):
            when = variant["when"]
            if "time_range_hours" in when:
                assert when["time_range_hours"] > 0
                assert when.get("stepType") != "instant", (
                    f"{_entry_label(entry)}/{variant['name']}: instant with time_range_hours"
                )


def test_registry_C4_no_duplicate_when(registry):
    for entry in registry:
        signatures = []
        for variant in entry.get("params", []):
            signature = tuple(sorted(variant["when"].items()))
            assert signature not in signatures, (
                f"{_entry_label(entry)}/{variant['name']}: duplicate when {dict(signature)}"
            )
            signatures.append(signature)


def test_registry_N2_no_when_less_variant(registry):
    for entry in registry:
        for variant in entry.get("params", []):
            assert variant.get("when"), (
                f"{_entry_label(entry)}/{variant['name']}: variant without when "
                f"(unconditional names belong to entry level)"
            )


def test_registry_L1_sorted(registry):
    keys = [
        (e["key"]["discipline"], e["key"]["category"], e["key"]["number"])
        for e in registry
    ]
    if keys != sorted(keys):
        warnings.warn("L1: entries are not sorted by (discipline, category, number)")


def test_registry_L2_wgrib2_name_uppercase(registry):
    for entry in registry:
        name = entry.get("wgrib2_name")
        if name is not None and name != name.upper():
            warnings.warn(f"L2: {_entry_label(entry)}: wgrib2_name {name!r} is not uppercase")


def test_registry_L3_step_type_values(registry):
    for entry in registry:
        for variant in entry.get("params", []):
            step_type = variant["when"].get("stepType")
            if step_type is not None and step_type not in STEP_TYPE_VALUES:
                warnings.warn(
                    f"L3: {_entry_label(entry)}/{variant['name']}: "
                    f"unexpected stepType {step_type!r}"
                )
