#!/usr/bin/env python3
"""Regenerate the small, frozen T09 synthetic GRIB2 execution fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import eccodes


REFERENCE_TIME = "2026-08-30T00:00:00Z"
LEADS = tuple(range(0, 73, 6))
LEVELS = (500, 850)
MEMBERS = (("control", 0, 0), ("perturbation", 1, 2), ("perturbation", 2, 3))
GRID = {"ni": 4, "nj": 3, "north": 50, "west": 100}


def _values(lead: int, level: int, member: int, count: int, *, change: int = 0) -> list[float]:
    base = 250 + lead // 6 + (0 if level == 500 else 20) + 40 * member + change
    return [float(base + cell) for cell in range(count)]


def _message(*, parameter: str, lead: int, level: int, member: int, member_type: int,
             ni: int = 4, change: int = 0) -> bytes:
    handle = eccodes.codes_grib_new_from_samples("regular_ll_pl_grib2")
    try:
        for key, value in (
            ("shortName", parameter), ("dataDate", 20260830), ("dataTime", 0),
            ("forecastTime", lead), ("typeOfLevel", "isobaricInhPa"), ("level", level),
            ("productDefinitionTemplateNumber", 1), ("typeOfEnsembleForecast", member_type),
            ("perturbationNumber", member), ("numberOfForecastsInEnsemble", 3),
            ("Ni", ni), ("Nj", GRID["nj"]),
            ("latitudeOfFirstGridPointInDegrees", GRID["north"]),
            ("latitudeOfLastGridPointInDegrees", GRID["north"] - GRID["nj"] + 1),
            ("longitudeOfFirstGridPointInDegrees", GRID["west"]),
            ("longitudeOfLastGridPointInDegrees", GRID["west"] + ni - 1),
            ("iDirectionIncrementInDegrees", 1), ("jDirectionIncrementInDegrees", 1),
        ):
            eccodes.codes_set(handle, key, value)
        values = _values(lead, level, member, ni * GRID["nj"], change=change)
        if parameter == "gh":
            values = [float(100 + cell) for cell in range(ni * GRID["nj"])]
        elif parameter == "z":
            values = [float(980 + cell) for cell in range(ni * GRID["nj"])]
        eccodes.codes_set_values(handle, values)
        return eccodes.codes_get_message(handle)
    finally:
        eccodes.codes_release(handle)


def _field(parameter: str, lead: int, level: int, member: int, role: str,
           *, ni: int = 4, change: int = 0) -> dict:
    values = _values(lead, level, member, ni * GRID["nj"], change=change)
    if parameter == "gh":
        values = [float(100 + cell) for cell in range(ni * GRID["nj"])]
    elif parameter == "z":
        values = [float(980 + cell) for cell in range(ni * GRID["nj"])]
    return {
        "parameter": parameter, "lead_hours": lead, "level_hpa": level,
        "member": {"id": str(member), "role": role}, "shape": [GRID["nj"], ni],
        "units": {"t": "K", "gh": "gpm", "z": "m**2 s**-2"}[parameter],
        "first_value": values[0], "last_value": values[-1],
    }


def build(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    files = []

    def write(name: str, fields: list[tuple[str, int, int, int, str, int, int, int]]) -> None:
        messages = []
        expected = []
        for parameter, lead, level, member, role, member_type, ni, change in fields:
            messages.append(_message(parameter=parameter, lead=lead, level=level,
                                     member=member, member_type=member_type, ni=ni, change=change))
            expected.append(_field(parameter, lead, level, member, role, ni=ni, change=change))
        payload = b"".join(messages)
        target = output_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        files.append({"path": name, "sha256": hashlib.sha256(payload).hexdigest(),
                      "size_bytes": len(payload), "fields": expected})

    baseline = []
    for lead in LEADS:
        for role, member, member_type in MEMBERS:
            name = f"baseline/f{lead:03d}_m{member}.grib2"
            # The field order changes; logical identity never depends on it.
            levels = LEVELS if (lead // 6 + member) % 2 == 0 else tuple(reversed(LEVELS))
            write(name, [("t", lead, level, member, role, member_type, 4, 0) for level in levels])
            baseline.append(name)

    write("cases/duplicate.grib2", [("t", 24, 850, 1, "perturbation", 2, 4, 0)])
    write("cases/missing_replacement.grib2", [("t", 48, 500, 2, "perturbation", 3, 4, 0)])
    write("cases/grid_conflict.grib2", [("t", 30, 500, 2, "perturbation", 3, 5, 0)])
    write("cases/unit_pair.grib2", [("gh", 36, 500, 0, "control", 0, 4, 0),
                                    ("z", 36, 500, 0, "control", 0, 4, 0)])
    write("cases/resource_updated.grib2", [("t", 42, level, 0, "control", 0, 4, 10)
                                              for level in LEVELS])
    return {
        "schema_version": 1, "origin": "synthetic ecCodes sample; no operational model provenance",
        "eccodes_api_version": eccodes.codes_get_api_version(),
        "sample": "regular_ll_pl_grib2", "reference_time": REFERENCE_TIME,
        "grid": GRID, "baseline_files": baseline, "files": files,
        "scenarios": {
            "shuffled": {"files": list(reversed(baseline)), "expected_fields": 78},
            "missing": {"replace": "baseline/f048_m2.grib2", "with": "cases/missing_replacement.grib2",
                        "missing": {"parameter": "t", "lead_hours": 48, "level_hpa": 850,
                                    "member": {"id": "2", "role": "perturbation"}}},
            "duplicate": {"add": "cases/duplicate.grib2", "duplicates": {
                "parameter": "t", "lead_hours": 24, "level_hpa": 850,
                "member": {"id": "1", "role": "perturbation"}}},
            "grid_conflict": {"add": "cases/grid_conflict.grib2", "conflicts_with": "baseline/f030_m2.grib2"},
            "unit_pair": {"file": "cases/unit_pair.grib2", "native_parameters": ["gh", "z"],
                          "units": ["gpm", "m**2 s**-2"]},
            "resource_updated": {"replace": "baseline/f042_m0.grib2", "with": "cases/resource_updated.grib2"},
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, help="write GRIB2 files outside the repository")
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("expected.json"))
    parser.add_argument("--check", action="store_true", help="generate in a temporary directory and verify expected.json")
    parser.add_argument("--update-manifest", action="store_true", help="intentionally replace the reference manifest")
    args = parser.parse_args()
    if args.check and (args.output_dir or args.update_manifest):
        parser.error("--check cannot be combined with --output-dir or --update-manifest")
    if not args.check and not args.output_dir:
        parser.error("--output-dir is required unless --check is used")
    if args.check:
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            actual = build(Path(temporary))
            expected = json.loads(args.manifest.read_text())
            if actual["eccodes_api_version"] == expected["eccodes_api_version"]:
                if actual != expected:
                    raise SystemExit("generated identities, values, or SHA256 differ from expected.json")
                print(f"verified {len(actual['files'])} generated GRIB2 files and their pinned SHA256 values")
            else:
                def semantic(manifest: dict) -> dict:
                    return {**manifest, "eccodes_api_version": None,
                            "files": [{key: value for key, value in file.items()
                                       if key not in {"sha256", "size_bytes"}}
                                      for file in manifest["files"]]}

                if semantic(actual) != semantic(expected):
                    raise SystemExit("generated field semantics differ from expected.json")
                print(f"verified {len(actual['files'])} generated field descriptors; "
                      "run pytest to check decoded values; pinned SHA256 requires ecCodes API "
                      + expected["eccodes_api_version"])
    else:
        manifest = build(args.output_dir)
        output_manifest = args.manifest if args.update_manifest else args.output_dir / "manifest.json"
        output_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        print(f"wrote {len(manifest['files'])} GRIB2 files and {output_manifest}")


if __name__ == "__main__":
    main()
