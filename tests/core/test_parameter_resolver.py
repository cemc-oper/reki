from types import MappingProxyType

import pandas as pd
import pytest

import reki
from reki.readers.grib.config import ParameterIndex, _load_document
from reki.readers.grib.reader import GribReader


def test_resolve_id_name_alias_and_external_name():
    by_id = reki.resolve_parameter("cedarkit.t2m")
    by_name = reki.resolve_parameter("t2m")
    by_alias = reki.resolve_parameter("tmax2m")
    by_external = reki.resolve_parameter("TMP")

    assert by_id.record.parameter_id == "cedarkit.t2m"
    assert by_id.matched_by == "parameter_id"
    assert by_name.record == by_id.record
    assert by_alias.record.parameter_id == "cedarkit.mx2t"
    assert by_external.record.parameter_id == "cedarkit.t"
    assert by_id.query.parameter == {"discipline": 0, "parameterCategory": 0, "parameterNumber": 0}
    assert by_id.query.level_type == "heightAboveGround"
    assert by_id.query.level == 2
    assert isinstance(by_id.record.grib_key, MappingProxyType)


def test_resolve_fixed_conditions_and_time_range():
    resolved = reki.resolve_parameter("cedarkit.u10mmax-3")
    assert resolved.query.step_type == "max"
    assert resolved.query.time_range == pd.Timedelta(hours=3)
    assert resolved.query.extra["typeOfFirstFixedSurface"] == 103
    assert resolved.query.extra["first_level"] == 10

    reader = object.__new__(GribReader)
    reader._query = resolved.query
    filters = reader._filters_from_query()
    assert filters["stepType"] == "max"
    assert filters["lengthOfTimeRange"] == 3
    assert "step_type" not in filters


def test_resolve_can_complete_generic_entry_conditions():
    resolved = reki.resolve_parameter("cedarkit.t", level_type="isobaricInhPa", level=500)
    assert resolved.query.level_type == "isobaricInhPa"
    assert resolved.query.level == 500


def test_namespaced_external_name_inherits_from_entry_without_reverse_input():
    inherited = reki.resolve_external_name("cedarkit.t2m", "cmadaas")
    direct = reki.resolve_external_name("cedarkit.t", "cmadaas")
    assert inherited.code == direct.code == "TEM"
    assert inherited.entry_parameter_id == "cedarkit.t"
    assert inherited.inherited is True
    with pytest.raises(reki.ParameterNotFoundError):
        reki.resolve_parameter("TEM")
    with pytest.raises(reki.ParameterExternalNameNotMappedError) as error:
        reki.resolve_external_name("cedarkit.td", "cmadaas")
    assert error.value.code == "cmadaas_name_not_mapped"
    with pytest.raises(reki.ParameterNamespaceNotFoundError):
        reki.resolve_external_name("cedarkit.t", "unknown")


def test_resolve_rejects_unknown_and_fixed_condition_conflicts():
    with pytest.raises(reki.ParameterNotFoundError) as error:
        reki.resolve_parameter("cedarkit.does-not-exist")
    assert error.value.code == "parameter_not_found"

    with pytest.raises(reki.ParameterConditionConflictError) as error:
        reki.resolve_parameter("cedarkit.t2m", level=10)
    assert error.value.code == "parameter_condition_conflict"


def test_snapshot_validation_rejects_same_priority_name_ambiguity():
    entries = [
        {"parameter_id": "cedarkit.a", "key": {"discipline": 0, "category": 0, "number": 1}, "name": "same"},
        {"parameter_id": "cedarkit.b", "key": {"discipline": 0, "category": 0, "number": 2}, "name": "same"},
    ]
    with pytest.raises(reki.ParameterAmbiguityError) as error:
        ParameterIndex(entries, api_version="reki.parameter-registry/v2")
    assert error.value.candidates == ("cedarkit.a", "cedarkit.b")


def test_v3_rejects_variant_external_name_override():
    entries = [{"parameter_id": "cedarkit.a", "key": {"discipline": 0, "category": 0, "number": 1}, "name": "a",
                "external_names": {"cmadaas": "AAA"},
                "params": [{"parameter_id": "cedarkit.a1", "name": "a1", "when": {"first_level_type": 1},
                            "external_names": {"cmadaas": "BBB"}}]}]
    with pytest.raises(ValueError, match="variants may not override"):
        ParameterIndex(entries, api_version="reki.parameter-registry/v3")


def test_legacy_v1_document_still_builds_a_name_index():
    index = _load_document([{
        "key": {"discipline": 0, "category": 0, "number": 0}, "name": "legacy",
    }])
    record, matched_by = index.resolve_record("legacy")
    assert record.parameter_id is None
    assert matched_by == "name"
