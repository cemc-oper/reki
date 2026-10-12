"""T07 frozen query-to-registry mapping without data access."""

import hashlib
import json
from importlib.resources import files
from pathlib import Path

import pandas as pd
import pytest

from cedarkit_query import AliasSnapshot, Query, QueryError
from reki.parameter_adapter import (
    FROZEN_REGISTRY_SHA256, frozen_vocabulary_snapshot, resolve_frozen_parameter,
)
from reki.readers.grib.config import resolve_external_name, resolve_parameter

CASES = json.loads((Path(__file__).parent / "fixtures/t07_parameter_cases.json").read_text())


def _query(case):
    return Query({"api_version": "cedarkit.query/v1", "domain": "grid", "dataset": CASES["dataset"],
                  "parameter": case["parameter_id"], "reference_time": CASES["reference_time"],
                  "lead_time": CASES["lead_time"], "vertical": {"type": "surface"},
                  "statistic": case["statistic"]})


def test_snapshot_hash_and_frozen_aliases():
    actual = hashlib.sha256(files("reki.readers.grib.config").joinpath("param_registry.yaml").read_bytes()).hexdigest()
    assert actual == CASES["registry_sha256"] == FROZEN_REGISTRY_SHA256
    snapshot = frozen_vocabulary_snapshot(registry_sha256=actual)
    assert snapshot.version == actual
    assert dict(snapshot.aliases["cmadaas"]) == {case["code"]: case["parameter_id"] for case in CASES["cases"]}
    assert "PRE" not in snapshot.aliases["cmadaas"]


@pytest.mark.parametrize("case", CASES["cases"], ids=lambda case: case["code"])
def test_frozen_case_uses_existing_resolvers_without_dropping_conditions(case):
    result = resolve_frozen_parameter(_query(case), registry_sha256=CASES["registry_sha256"])
    assert result.query.parameter == case["parameter_id"]
    assert result.external_code == resolve_external_name(case["parameter_id"], "cmadaas").code == case["code"]
    assert result.field_query.parameter == {
        "discipline": case["grib_key"][0], "parameterCategory": case["grib_key"][1],
        "parameterNumber": case["grib_key"][2],
    }
    assert result.field_query.level_type == "surface"
    assert result.field_query.extra["typeOfFirstFixedSurface"] == 1
    assert result.field_query.step_type == case["statistic"]["kind"]
    assert result.field_query.time_range == (pd.Timedelta(hours=24) if case["statistic"]["kind"] == "accum" else None)
    assert resolve_parameter(case["parameter_id"]).record.unit == case["registry_unit"]


def test_explicit_alias_snapshot_produces_same_stable_query():
    case = CASES["cases"][0]
    stable = resolve_frozen_parameter(_query(case), registry_sha256=CASES["registry_sha256"])
    alias = _query(case).to_dict()
    alias["parameter"] = {"namespace": "cmadaas", "name": "TEM"}
    snapshot = frozen_vocabulary_snapshot(registry_sha256=CASES["registry_sha256"])
    mapped = resolve_frozen_parameter(alias, registry_sha256=CASES["registry_sha256"], vocabulary_snapshot=snapshot)
    assert mapped.query == stable.query
    with pytest.raises(QueryError) as caught:
        resolve_frozen_parameter(alias, registry_sha256=CASES["registry_sha256"])
    assert (caught.value.code, caught.value.path) == ("unknown_parameter", "/query/parameter")


def test_changed_or_ambiguous_alias_snapshot_cannot_silently_rebind_code():
    value = _query(CASES["cases"][0]).to_dict()
    value["parameter"] = {"namespace": "cmadaas", "name": "TEM"}
    changed = AliasSnapshot(CASES["registry_sha256"], {"cmadaas": {"TEM": "cedarkit.h.any"}})
    with pytest.raises(QueryError) as caught:
        resolve_frozen_parameter(value, registry_sha256=CASES["registry_sha256"], vocabulary_snapshot=changed)
    assert (caught.value.code, caught.value.path) == ("unsupported", "/vocabulary_version")
    ambiguous = AliasSnapshot(CASES["registry_sha256"],
                              {"cmadaas": {"TEM": ("cedarkit.t", "cedarkit.h.any")}})
    with pytest.raises(QueryError) as caught:
        resolve_frozen_parameter(value, registry_sha256=CASES["registry_sha256"], vocabulary_snapshot=ambiguous)
    assert (caught.value.code, caught.value.path) == ("ambiguous_mapping", "/query/parameter")


@pytest.mark.parametrize("mutate,path", [
    (lambda q: q.update(dataset="cma_gfs_gmf"), "/query/dataset"),
    (lambda q: q.update(reference_time="2026-08-31T00:00:00Z"), "/query/reference_time"),
    (lambda q: q.update(lead_time="PT12H"), "/query/lead_time"),
    (lambda q: q.update(vertical={"type": "isobaric", "unit": "hPa", "values": 500}), "/query/vertical"),
    (lambda q: q.update(statistic={"kind": "accum", "window": "PT24H"}), "/query/statistic"),
    (lambda q: q.update(member={"role": "control", "id": "0"}), "/query/member"),
    (lambda q: q.update(parameter=["cedarkit.t", "cedarkit.h.any"]), "/query"),
])
def test_unverified_query_shape_is_rejected(mutate, path):
    value = _query(CASES["cases"][0]).to_dict()
    mutate(value)
    with pytest.raises(QueryError) as caught:
        resolve_frozen_parameter(value, registry_sha256=CASES["registry_sha256"])
    assert (caught.value.code, caught.value.path) == ("unsupported", path)


@pytest.mark.parametrize("parameter,code", [
    ("cedarkit.pwat.any", "unmapped_parameter"),
    ("cedarkit.rain.any", "unsupported"),
    ("cedarkit.does-not-exist", "unknown_parameter"),
])
def test_pre_conflict_and_unknown_parameter_do_not_guess(parameter, code):
    value = _query(CASES["cases"][0]).to_dict()
    value["parameter"] = parameter
    with pytest.raises(QueryError) as caught:
        resolve_frozen_parameter(value, registry_sha256=CASES["registry_sha256"])
    assert (caught.value.code, caught.value.path) == (code, "/query/parameter")


@pytest.mark.parametrize("parameter", ["CPE03", "CPE06", "CPE12", "CPE24", "LPE03", "LPE24"])
def test_derived_precipitation_codes_are_not_reverse_mapped(parameter):
    value = _query(CASES["cases"][2]).to_dict()
    value["parameter"] = parameter
    with pytest.raises(QueryError) as caught:
        resolve_frozen_parameter(value, registry_sha256=CASES["registry_sha256"])
    assert (caught.value.code, caught.value.path) == ("unknown_parameter", "/query/parameter")


def test_precipitation_window_is_independent_from_lead_time():
    value = _query(CASES["cases"][2]).to_dict()
    value["statistic"]["window"] = "PT12H"
    with pytest.raises(QueryError) as caught:
        resolve_frozen_parameter(value, registry_sha256=CASES["registry_sha256"])
    assert (caught.value.code, caught.value.path) == ("unsupported", "/query/statistic")


def test_registry_mismatch_rejected_before_resolution():
    with pytest.raises(QueryError) as caught:
        resolve_frozen_parameter(_query(CASES["cases"][0]), registry_sha256="0" * 64)
    assert (caught.value.code, caught.value.path) == ("unsupported", "/vocabulary_version")
