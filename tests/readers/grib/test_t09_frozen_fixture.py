"""Verify the frozen multi-file GRIB2 fixture with real ecCodes decoding."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import eccodes
import numpy as np
import pytest

from reki.readers.grib.reader import GribReader


FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "t09"
MANIFEST = json.loads((FIXTURE / "expected.json").read_text())


@pytest.fixture(scope="module")
def generated_files(tmp_path_factory):
    spec = importlib.util.spec_from_file_location("t09_generate", FIXTURE / "generate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path_factory.mktemp("t09-grib")
    generated = module.build(output)
    assert [item["path"] for item in generated["files"]] == [item["path"] for item in MANIFEST["files"]]
    return output


def _identity(field: dict) -> tuple:
    return (field["parameter"], field["lead_hours"], field["level_hpa"],
            field["member"]["role"], field["member"]["id"])


def _decode(path: Path) -> list[dict]:
    result = []
    with path.open("rb") as stream:
        while (handle := eccodes.codes_grib_new_from_file(stream)) is not None:
            try:
                member = eccodes.codes_get(handle, "perturbationNumber")
                member_type = eccodes.codes_get(handle, "typeOfEnsembleForecast")
                values = eccodes.codes_get_values(handle)
                result.append({
                    "parameter": eccodes.codes_get(handle, "shortName"),
                    "reference_date": eccodes.codes_get(handle, "dataDate"),
                    "reference_time": eccodes.codes_get(handle, "dataTime"),
                    "lead_hours": eccodes.codes_get(handle, "forecastTime"),
                    "level_hpa": eccodes.codes_get(handle, "level"),
                    "member": {"id": str(member),
                               "role": "control" if member_type == 0 else "perturbation"},
                    "member_type": member_type,
                    "shape": [eccodes.codes_get(handle, "Nj"), eccodes.codes_get(handle, "Ni")],
                    "units": eccodes.codes_get(handle, "units"),
                    "values": values,
                })
            finally:
                eccodes.codes_release(handle)
    return result


def test_generated_sha256_headers_and_values_cover_all_78_combinations(generated_files):
    records = {item["path"]: item for item in MANIFEST["files"]}
    assert len(records) == 44
    assert len(MANIFEST["baseline_files"]) == 39
    identities = set()
    for name, record in records.items():
        path = generated_files / name
        if eccodes.codes_get_api_version() == MANIFEST["eccodes_api_version"]:
            assert path.stat().st_size == record["size_bytes"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
        decoded = _decode(path)
        assert len(decoded) == len(record["fields"])
        for actual, expected in zip(decoded, record["fields"]):
            assert actual["reference_date"] == 20260830
            assert actual["reference_time"] == 0
            for key in ("parameter", "lead_hours", "level_hpa", "member", "shape", "units"):
                assert actual[key] == expected[key]
            assert actual["member_type"] == {"0": 0, "1": 2, "2": 3}[expected["member"]["id"]]
            assert np.array_equal(actual["values"][[0, -1]],
                                  [expected["first_value"], expected["last_value"]])
            assert np.array_equal(np.diff(actual["values"]), np.ones(len(actual["values"]) - 1))
            if name in MANIFEST["baseline_files"]:
                assert _identity(actual) not in identities
                identities.add(_identity(actual))
    assert len(identities) == 78
    assert identities == {("t", lead, level, role, str(member))
                          for lead in range(0, 73, 6) for level in (500, 850)
                          for role, member in (("control", 0), ("perturbation", 1), ("perturbation", 2))}


def test_scenarios_expose_missing_duplicate_grid_unit_and_resource_change():
    records = {item["path"]: item for item in MANIFEST["files"]}
    baseline = MANIFEST["baseline_files"]
    reversed_ids = {_identity(field) for name in reversed(baseline)
                    for field in records[name]["fields"]}
    assert len(reversed_ids) == 78

    missing = MANIFEST["scenarios"]["missing"]
    original = {_identity(field) for field in records[missing["replace"]]["fields"]}
    replacement = {_identity(field) for field in records[missing["with"]]["fields"]}
    assert original - replacement == {_identity(missing["missing"])}

    duplicate = MANIFEST["scenarios"]["duplicate"]
    duplicate_field = records[duplicate["add"]]["fields"][0]
    assert _identity(duplicate_field) == _identity(duplicate["duplicates"])
    assert _identity(duplicate_field) in reversed_ids

    grid = MANIFEST["scenarios"]["grid_conflict"]
    conflict = records[grid["add"]]["fields"][0]
    original_grid = next(field for field in records[grid["conflicts_with"]]["fields"]
                         if _identity(field) == _identity(conflict))
    assert original_grid["shape"] == [3, 4]
    assert conflict["shape"] == [3, 5]

    units = records[MANIFEST["scenarios"]["unit_pair"]["file"]]["fields"]
    assert [(field["parameter"], field["units"]) for field in units] == [
        ("gh", "gpm"), ("z", "m**2 s**-2")]

    updated = MANIFEST["scenarios"]["resource_updated"]
    old = records[updated["replace"]]
    new = records[updated["with"]]
    assert old["sha256"] != new["sha256"]
    assert {_identity(field) for field in old["fields"]} == {_identity(field) for field in new["fields"]}
    assert all(new_field["first_value"] == old_field["first_value"] + 10
               for old_field, new_field in zip(sorted(old["fields"], key=_identity),
                                                sorted(new["fields"], key=_identity)))


def test_reki_reader_decodes_generated_multifield_file(generated_files):
    path = generated_files / "baseline/f024_m1.grib2"
    fields = GribReader(None, path, index_policy="off").all()
    assert len(fields) == 2
    field = fields.sel(parameter="t", level_type="pl", level=850).one()
    assert field.metadata.member == 1
    assert field.to_xarray().shape == (3, 4)
    assert np.array_equal(field.to_xarray().values.ravel(), np.arange(314, 326))


def test_resource_update_replaces_same_path_and_changes_fingerprint(tmp_path, generated_files):
    scenario = MANIFEST["scenarios"]["resource_updated"]
    target = tmp_path / "active.grib2"
    shutil.copyfile(generated_files / scenario["replace"], target)
    original = hashlib.sha256(target.read_bytes()).hexdigest()
    replacement = tmp_path / "replacement.grib2"
    shutil.copyfile(generated_files / scenario["with"], replacement)
    replacement.replace(target)
    assert hashlib.sha256(target.read_bytes()).hexdigest() != original
    assert [field.metadata.level for field in GribReader(None, target, index_policy="off").all()] == [500, 850]
