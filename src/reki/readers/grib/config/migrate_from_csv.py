"""
One-off migration: CSV param tables -> param_registry.yaml.

Implements rules M1-M8 of ``param_registry_spec.md`` (appendix C):

- M1 group cemc-param-table.csv by (discipline, category, number), keep file order in group
- M2 promote the unconditional row (or first canonical row) to entry-level ``name``
- M3 join wgrib2_short_name.csv as entry-level ``wgrib2_name``
- M4 merge ``alias=TRUE`` rows into the canonical row's ``aliases``
- M5 non-empty condition columns become ``when``
- M6 legacy ``typeOfLevel``/``level`` columns are kept as informational fields
- M7 names ending with ``#<N>`` get ``time_range_hours: N`` in ``when``
- M8 ``--verify`` cross-checks old tables vs new registry

Usage::

    python -m reki.readers.grib.config.migrate_from_csv generate
    python -m reki.readers.grib.config.migrate_from_csv verify

Kept for provenance. Re-running ``generate`` requires the two source CSVs,
which were removed after the migration; restore them from git history.
"""

import argparse
import math
import re
import sys
from pathlib import Path

import pandas as pd
import yaml

CONFIG_DIR = Path(__file__).parent
CEMC_CSV = CONFIG_DIR / "cemc-param-table.csv"
WGRIB2_CSV = CONFIG_DIR / "wgrib2_short_name.csv"
REGISTRY_YAML = CONFIG_DIR / "param_registry.yaml"

CONDITION_COLUMNS = [
    "first_level_type",
    "first_level",
    "second_level_type",
    "second_level",
    "stepType",
]
METADATA_COLUMNS = ["unit", "description", "description_cn"]
INFO_COLUMNS = ["typeOfLevel", "level"]

TIME_RANGE_PATTERN = re.compile(r"#(\d+)$")


def _isna(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value)) or pd.isna(value)


def _scalar(value):
    """Convert a CSV cell to a YAML-friendly scalar, NaN -> None."""
    if _isna(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _condition_signature(row) -> tuple:
    return tuple(_scalar(row[col]) for col in CONDITION_COLUMNS)


def _build_when(row) -> dict:
    when = {}
    for col in CONDITION_COLUMNS:
        value = _scalar(row[col])
        if value is not None:
            when[col] = value
    match = TIME_RANGE_PATTERN.search(row["name"])
    if match:  # M7
        when["time_range_hours"] = int(match.group(1))
    return when


def _build_entry(key: tuple, group: pd.DataFrame) -> dict:
    """Build one registry entry from a cemc CSV group (M1, M2, M4-M6)."""
    canonical = group[~group["alias"]]
    alias_rows = group[group["alias"]]

    # M4: attach each alias row to the last canonical row with identical conditions.
    alias_map: dict[int, list] = {idx: [] for idx in canonical.index}
    for _, alias_row in alias_rows.iterrows():
        signature = _condition_signature(alias_row)
        targets = [
            idx for idx, row in canonical.iterrows()
            if _condition_signature(row) == signature
        ]
        if not targets:
            raise ValueError(f"alias row {alias_row['name']!r} has no canonical row with same conditions")
        alias_map[targets[-1]].append(alias_row["name"])

    # M2: promote the unconditional row, or the first canonical row, to entry level.
    unconditional = [
        idx for idx, row in canonical.iterrows()
        if all(v is None for v in _condition_signature(row))
    ]
    if len(unconditional) > 1:
        names = [canonical.loc[idx, "name"] for idx in unconditional]
        raise ValueError(f"{key}: multiple unconditional rows: {names}")
    promoted_idx = unconditional[0] if unconditional else canonical.index[0]
    promoted = canonical.loc[promoted_idx]

    entry: dict = {"key": {"discipline": key[0], "category": key[1], "number": key[2]}}
    entry["name"] = promoted["name"]
    for col in METADATA_COLUMNS + INFO_COLUMNS:
        value = _scalar(promoted[col])
        if value is not None:
            entry[col] = value
    # a promoted unconditional row is removed from params; keep its aliases at entry level
    if unconditional and alias_map[promoted_idx]:
        entry["aliases"] = alias_map[promoted_idx]

    params = []
    for idx, row in canonical.iterrows():
        # the promoted row stays in params only when it carries conditions (M2 case 2)
        if idx == promoted_idx and unconditional:
            continue
        when = _build_when(row)
        if not when:
            raise ValueError(f"{key}: row {row['name']!r} would be a when-less variant (V2)")
        variant: dict = {"name": row["name"]}
        if alias_map[idx]:
            variant["aliases"] = alias_map[idx]
        variant["when"] = when
        # informational legacy columns (M6)
        for col in INFO_COLUMNS:
            value = _scalar(row[col])
            if value is not None:
                variant[col] = value
        # variant metadata only when it differs from entry level (inheritance)
        for col in METADATA_COLUMNS:
            value = _scalar(row[col])
            if value is not None and value != entry.get(col):
                variant[col] = value
        params.append(variant)

    # M7b: for every ``#<N>``-suffixed variant, ensure a base variant without the
    # time_range_hours condition exists (mirrors the u10mmax pattern).
    existing_names = {v["name"] for v in params}
    synthesized = []
    for i, variant in enumerate(params):
        match = TIME_RANGE_PATTERN.search(variant["name"])
        if not match:
            continue
        base_name = variant["name"][: match.start()]
        if base_name in existing_names:
            continue
        existing_names.add(base_name)
        base_when = {k: v for k, v in variant["when"].items() if k != "time_range_hours"}
        base_variant = {"name": base_name, "when": base_when}
        for col in INFO_COLUMNS + METADATA_COLUMNS:
            if col in variant and col not in ("description", "description_cn"):
                base_variant[col] = variant[col]
        synthesized.append((i, base_variant))
    for i, base_variant in reversed(synthesized):
        params.insert(i, base_variant)

    if params:
        entry["params"] = params
    return entry


def generate() -> list:
    cemc = pd.read_csv(CEMC_CSV)
    wgrib2 = pd.read_csv(WGRIB2_CSV)

    entries: dict[tuple, dict] = {}
    for key, group in cemc.groupby(["discipline", "category", "number"], sort=False):
        entries[tuple(int(k) for k in key)] = _build_entry(tuple(int(k) for k in key), group)

    # M3: join wgrib2 short names
    for _, row in wgrib2.iterrows():
        key = (int(row["discipline"]), int(row["parameterCategory"]), int(row["parameterNumber"]))
        if key in entries:
            entries[key]["wgrib2_name"] = row["short_name"]
        else:
            entries[key] = {
                "key": {"discipline": key[0], "category": key[1], "number": key[2]},
                "name": row["short_name"],
                "wgrib2_name": row["short_name"],
            }

    # F3: sort entries by triple
    ordered = [entries[k] for k in sorted(entries)]

    # place wgrib2_name right after name for readability
    def reorder(entry: dict) -> dict:
        result = {}
        for field in ("key", "name", "aliases", "wgrib2_name", "unit", "description",
                      "description_cn", "typeOfLevel", "level", "params"):
            if field in entry:
                result[field] = entry[field]
        return result

    ordered = [reorder(e) for e in ordered]

    with open(REGISTRY_YAML, "w", encoding="utf-8") as f:
        f.write("# GRIB2 要素注册表。约束规范见同目录 param_registry_spec.md，请勿违反编号规则。\n")
        f.write("# 本文件由 migrate_from_csv.py 从 cemc-param-table.csv / wgrib2_short_name.csv 迁移生成。\n")
        yaml.safe_dump(
            ordered, f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=120,
        )
    print(f"generated {REGISTRY_YAML} with {len(ordered)} entries")
    return ordered


# ---------------------------------------------------------------------------
# verify: cross-check old CSV tables vs new registry (M8)
# ---------------------------------------------------------------------------

def _old_tables():
    cemc = pd.read_csv(CEMC_CSV)
    wgrib2 = pd.read_csv(WGRIB2_CSV)
    return cemc, wgrib2


def _old_check_value(expected, actual) -> bool:
    if expected is None or pd.isna(expected):
        return True
    if actual == "undef" or actual is None:
        return False
    return expected == actual


def _old_find_short_name(cemc, wgrib2, d, c, n):
    df = wgrib2.query(f"discipline=={d} & parameterCategory=={c} & parameterNumber=={n}")
    if not df.empty:
        return df.iloc[0]["short_name"]
    df = cemc.query(f"discipline=={d} & category=={c} & number=={n}")
    if not df.empty:
        return df.iloc[0]["name"]
    return None


def _old_find_wgrib2_name(wgrib2, key) -> object:
    df = wgrib2.query(
        f"discipline=={key.discipline} & parameterCategory=={key.category} & parameterNumber=={key.number}"
    )
    return None if df.empty else df.iloc[0]["short_name"]


def _old_find_cemc_name(cemc, key):
    df = cemc.query(f"discipline=={key.discipline} & category=={key.category} & number=={key.number}")
    df = df[~df["alias"]]
    selected = []
    for _, row in df.iterrows():
        if not all([
            _old_check_value(row["stepType"], key.stepType),
            _old_check_value(row["first_level_type"], key.first_level_type),
            _old_check_value(row["second_level_type"], key.second_level_type),
            _old_check_value(row["first_level"], key.first_level),
            _old_check_value(row["second_level"], key.second_level),
        ]):
            continue
        selected.append(row)
    return None if not selected else selected[-1]["name"]


def _old_convert_parameter(cemc, wgrib2, parameter: str):
    df = wgrib2[wgrib2["short_name"] == parameter]
    if not df.empty:
        row = df.iloc[0]
        return {
            "discipline": row["discipline"],
            "parameterCategory": row["parameterCategory"],
            "parameterNumber": row["parameterNumber"],
        }
    df = cemc[cemc["name"] == parameter]
    if not df.empty:
        row = df.iloc[0]
        result = {
            "discipline": float(row["discipline"]),
            "parameterCategory": float(row["category"]),
            "parameterNumber": float(row["number"]),
        }
        if not pd.isna(row["typeOfLevel"]):
            result["typeOfLevel"] = row["typeOfLevel"]
        if not pd.isna(row["level"]):
            result["level"] = row["level"]
        if not pd.isna(row["first_level"]):
            result["first_level"] = float(row["first_level"])
        if not pd.isna(row["second_level"]):
            result["second_level"] = float(row["second_level"])
        if not pd.isna(row["stepType"]):
            result["stepType"] = row["stepType"]
        return result
    return parameter


def verify() -> int:
    from reki.readers.grib.config import (
        GribParameterKey,
        find_short_name,
        find_wgrib2_name,
        find_cemc_name,
        get_param_registry,
    )
    from reki.readers.grib.common._parameter import convert_parameter

    cemc, wgrib2 = _old_tables()
    registry = get_param_registry()
    failures = []

    def check(label, actual, expected):
        if actual != expected:
            failures.append(f"{label}: new={actual!r} expected={expected!r}")

    triples = sorted(registry)
    # condition combos per triple: every canonical row's signature + empty + bogus
    for triple in triples:
        d, c, n = triple
        group = cemc.query(f"discipline=={d} & category=={c} & number=={n}")
        signatures = {tuple(None for _ in CONDITION_COLUMNS), (250, 999, None, None, None)}
        for _, row in group[~group["alias"]].iterrows():
            signatures.add(_condition_signature(row))

        for sig in signatures:
            key = GribParameterKey(
                discipline=d, category=c, number=n,
                first_level_type=sig[0], first_level=sig[1],
                second_level_type=sig[2], second_level=sig[3],
                stepType=sig[4],
            )
            check(f"find_wgrib2_name{triple, sig}",
                  find_wgrib2_name(key), _old_find_wgrib2_name(wgrib2, key))

            old_cemc = _old_find_cemc_name(cemc, key)
            new_cemc = find_cemc_name(key)
            if old_cemc is not None:
                # M8 exemption: a '#'-suffixed old result was a row-order
                # coincidence; the synthesized base name is the sanctioned answer.
                if new_cemc != old_cemc and new_cemc != old_cemc.split("#")[0]:
                    failures.append(
                        f"find_cemc_name{triple, sig}: new={new_cemc!r} expected={old_cemc!r}"
                    )
            else:
                # M8 exemption: generic-name fallback
                check(f"find_cemc_name-fallback{triple, sig}", new_cemc, registry[triple]["name"])

        # find_short_name: CEMC generic name preferred (M8 exemption over wgrib2-first)
        group_canonical = group[~group["alias"]] if not group.empty else group
        if not group_canonical.empty:
            unconditional = [
                row["name"] for _, row in group_canonical.iterrows()
                if all(v is None for v in _condition_signature(row))
            ]
            expected_short = unconditional[0] if unconditional else group_canonical.iloc[0]["name"]
        else:
            expected_short = _old_find_short_name(cemc, wgrib2, d, c, n)
        check(f"find_short_name{triple}", find_short_name(d, c, n), expected_short)

    # convert_parameter: exact dict equality for every known name
    names = list(wgrib2["short_name"]) + list(cemc["name"])
    for name in names:
        check(f"convert_parameter({name!r})",
              convert_parameter(name), _old_convert_parameter(cemc, wgrib2, name))

    if failures:
        print(f"VERIFY FAILED: {len(failures)} mismatches")
        for line in failures[:50]:
            print(" ", line)
        return 1
    print(f"verify OK: {len(triples)} entries, {len(names)} names cross-checked")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["generate", "verify"])
    args = parser.parse_args()
    if args.command == "generate":
        generate()
        return 0
    return verify()


if __name__ == "__main__":
    sys.exit(main())
