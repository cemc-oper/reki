"""Finite rule mechanisms, all native records and product declarations SYNTHETIC."""

from copy import deepcopy
from types import SimpleNamespace
from decimal import Decimal
import pytest

from cedarkit_query import QueryError, SourceError
from reki.translation import grib, cmadaas
from reki.translation.common import value_unit


@pytest.fixture
def native():
    return dict(
        edition=2,
        centre=98,
        subCentre=0,
        tablesVersion=4,
        localTablesVersion=0,
        productDefinitionTemplateNumber=0,
        significanceOfReferenceTime=1,
        year=2026,
        month=1,
        day=1,
        hour=0,
        minute=0,
        second=0,
        indicatorOfUnitOfTimeRange=1,
        forecastTime=6,
        typeOfFirstFixedSurface=100,
        scaleFactorOfFirstFixedSurface=0,
        scaledValueOfFirstFixedSurface=85000,
        typeOfSecondFixedSurface=255,
    )


def interval(native, template=8):
    return {
        **native,
        "productDefinitionTemplateNumber": template,
        "forecastTime": 24,
        "numberOfTimeRange": 1,
        "typeOfTimeIncrement": 2,
        "indicatorOfUnitForTimeRange": 1,
        "lengthOfTimeRange": 24,
        "yearOfEndOfOverallTimeInterval": 2026,
        "monthOfEndOfOverallTimeInterval": 1,
        "dayOfEndOfOverallTimeInterval": 3,
        "hourOfEndOfOverallTimeInterval": 0,
        "minuteOfEndOfOverallTimeInterval": 0,
        "secondOfEndOfOverallTimeInterval": 0,
        "typeOfStatisticalProcessing": 1,
    }


@pytest.mark.parametrize("factor,value", [(0, 85000), (1, 850000), (-1, 8500)])
def test_grib_vertical_equivalent_encodings(native, factor, value):
    record = {
        **native,
        "scaleFactorOfFirstFixedSurface": factor,
        "scaledValueOfFirstFixedSurface": value,
    }
    assert grib.fixed_surfaces(record) == dict(
        level_type="pressure", level=850, level_unit="hPa"
    )


def test_vertical_layer_order_and_missing_second_are_distinct(native):
    depth = {
        **native,
        "typeOfFirstFixedSurface": 106,
        "scaleFactorOfFirstFixedSurface": 1,
        "scaledValueOfFirstFixedSurface": 1,
        "typeOfSecondFixedSurface": 106,
        "scaleFactorOfSecondFixedSurface": 1,
        "scaledValueOfSecondFixedSurface": 4,
    }
    assert grib.fixed_surfaces(depth)["layer"]["bottom"]["value"] == 0.4
    assert grib.fixed_surfaces(depth)["layer"]["top"]["value"] == 0.1
    del depth["typeOfSecondFixedSurface"]
    with pytest.raises(SourceError) as exc:
        grib.fixed_surfaces(depth)
    assert exc.value.context["reason"] == "missing_native_metadata"


def test_named_surface_and_hybrid_need_no_fabricated_values(native):
    assert grib.fixed_surfaces({**native, "typeOfFirstFixedSurface": 1}) == {
        "level_type": "surface"
    }
    hybrid = {
        **native,
        "typeOfFirstFixedSurface": 105,
        "scaledValueOfFirstFixedSurface": 7,
    }
    with pytest.raises(QueryError) as exc:
        grib.fixed_surfaces(hybrid)
    assert exc.value.context["reason"] == "missing_context"
    assert grib.fixed_surfaces(
        hybrid, vertical_definition={"id": "SYNTHETIC.hybrid"}
    ) == {"level_type": "model_level", "level": 7}


@pytest.mark.parametrize("template", sorted(grib.TEMPLATES))
def test_target_template_time_paths_preserve_interval_end(native, template):
    record = (
        interval(native, template)
        if template in grib.INTERVAL_TEMPLATES
        else {**native, "productDefinitionTemplateNumber": template}
    )
    identity, window = grib.time_fields(record)
    assert identity["step"] == ("PT172800S" if window else "PT21600S")
    assert identity["valid_time"] == (
        "2026-01-03T00:00:00Z" if window else "2026-01-01T06:00:00Z"
    )
    if window:
        assert window == {
            "start": "2026-01-02T00:00:00Z",
            "end": "2026-01-03T00:00:00Z",
        }


@pytest.mark.parametrize(
    "unit,value,seconds",
    [
        (13, 31, 31),
        (0, 2, 120),
        (1, 2, 7200),
        (2, 1, 86400),
        (10, 1, 10800),
        (11, 1, 21600),
        (12, 1, 43200),
    ],
)
def test_fixed_time_units_are_exact(native, unit, value, seconds):
    identity, _ = grib.time_fields(
        {**native, "indicatorOfUnitOfTimeRange": unit, "forecastTime": value}
    )
    assert identity["step"] == f"PT{seconds}S"


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"month": 13}, "invalid_time_metadata"),
        ({"indicatorOfUnitOfTimeRange": 3}, "unsupported_native_encoding"),
        ({"productDefinitionTemplateNumber": 40}, "unsupported_native_encoding"),
        ({"significanceOfReferenceTime": 2}, "unsupported_native_encoding"),
        ({"forecastTime": -1}, "unsupported_native_encoding"),
        ({"forecastTime": None}, "missing_native_metadata"),
    ],
)
def test_time_diagnostics_do_not_turn_unknowns_into_missing_fields(
    native, changes, reason
):
    with pytest.raises(SourceError) as exc:
        grib.time_fields({**native, **changes})
    assert exc.value.context["reason"] == reason and "report" not in exc.value.to_dict()


def test_multiple_time_ranges_not_flattened_and_inconsistent_end_rejected(native):
    record = interval(native)
    with pytest.raises(SourceError) as exc:
        grib.time_fields({**record, "numberOfTimeRange": 2})
    assert exc.value.context["reason"] == "unsupported_native_encoding"
    with pytest.raises(SourceError) as exc:
        grib.time_fields({**record, "lengthOfTimeRange": 12})
    assert exc.value.context["reason"] == "inconsistent_native_metadata"


def test_grib_member_joint_numbering_and_role_conflict(native):
    config = SimpleNamespace(
        member_role=lambda n: "control" if n == 0 else "perturbation"
    )
    record = {
        **native,
        "productDefinitionTemplateNumber": 1,
        "perturbationNumber": 1,
        "typeOfEnsembleForecast": 3,
    }
    with pytest.raises(QueryError):
        grib.member(record, config)
    assert grib.member(record, config, numbering={(3, 1): 2}) == {
        "member": 2,
        "member_role": "perturbation",
    }
    with pytest.raises(SourceError) as exc:
        grib.member(record, config, numbering={(3, 1): 0})
    assert exc.value.context["reason"] == "inconsistent_native_metadata"
    with pytest.raises(SourceError) as exc:
        grib.member({**record, "perturbationNumber": -1}, config, numbering={})
    assert exc.value.context["reason"] == "invalid_member_metadata"
    assert grib.member({**native, "productDefinitionTemplateNumber": 2}, config) == {}


def test_native_statistical_window_must_match_fixed_period(native):
    record = interval(native)
    identity, window = grib.time_fields(record)
    stats = {
        "over": "time",
        "operation": "accumulation",
        "period": {"kind": "trailing", "duration": "PT24H"},
    }
    assert (
        grib.statistics(record, {"statistics": stats}, identity, window)["period"][
            "duration"
        ]
        == "PT86400S"
    )
    with pytest.raises(SourceError) as exc:
        grib.statistics(
            record,
            {"statistics": {**stats, "period": {"kind": "since_initialization"}}},
            identity,
            window,
        )
    assert exc.value.context["reason"] == "fixed_definition_mismatch"
    with pytest.raises(QueryError):
        grib.statistics(record, {}, identity, window)


def test_ensemble_quantile_requires_object_population_method_and_valid_percentile(
    native,
):
    record = {**native, "productDefinitionTemplateNumber": 6, "percentileValue": 90}
    identity, _ = grib.time_fields(record)
    stats = {
        "over": "ensemble",
        "operation": "quantile",
        "quantile": 0.9,
        "of": {"parameter_id": "SYNTHETIC.t"},
        "population": {"ref": "SYNTHETIC.all"},
        "method": {"kind": "empirical_inverse_cdf", "weighting": "equal"},
    }
    resources = SimpleNamespace(
        parameter=lambda name: {
            "fixed_conditions": {
                "statistics": {"over": "time", "operation": "instantaneous"}
            }
        }
    )
    product = {"populations": [{"id": "SYNTHETIC.all", "members": [0, 1, 2]}]}
    assert (
        grib.statistics(
            record,
            {"statistics": stats},
            identity,
            None,
            resources=resources,
            product=product,
        )
        == stats
    )
    with pytest.raises(SourceError) as exc:
        grib.statistics(
            {**record, "percentileValue": 101},
            {"statistics": stats},
            identity,
            None,
            resources=resources,
            product=product,
        )
    assert exc.value.context["reason"] == "invalid_statistics_metadata"


def test_unit_requirement_does_not_convert_values_or_guess_source():
    requirement = value_unit("degC", "K", quantity_kind="absolute_temperature")
    assert requirement.scale == Decimal(1) and requirement.offset == Decimal("273.15")
    assert value_unit("%", "1").scale == Decimal(".01")
    assert (
        value_unit(
            None,
            "K",
            {"rule": "common.value_unit", "config": {"source_unit": "kelvin"}},
        ).source
        == "K"
    )
    with pytest.raises(QueryError):
        value_unit("degC", "K")
    with pytest.raises(SourceError) as exc:
        value_unit(
            "degC", "K", {"rule": "common.value_unit", "config": {"source_unit": "K"}}
        )
    assert exc.value.context["reason"] == "inconsistent_native_metadata"
    with pytest.raises(SourceError):
        value_unit(None, "K")


@pytest.fixture
def contract():
    return cmadaas.InterfaceContract(
        "SYNTHETIC.single-grid",
        1,
        "SYNTHETIC.interface",
        "SYNTHETIC.gridMethod",
        {
            "time": "time",
            "step": "validTime",
            "level_type": "levelType",
            "level": "fcstLevel",
            "member": "fcstMember",
        },
        {
            "time": "time",
            "step": "validTime",
            "level_type": "levelType",
            "level": "fcstLevel",
            "member": "fcstMember",
        },
        "level_type_and_level",
        "canonical",
    )


def call(contract, **parameters):
    params = {
        "dataCode": "SYNTHETIC",
        "fcstEle": "SYNTHETIC.T",
        "time": "20260101080000",
        "validTime": "48",
        "levelType": "TYPE",
        "fcstLevel": "1000.0",
        **parameters,
    }
    response = {
        "response_kind": "RetGridArray2D",
        "record_count": 1,
        "request_parameters": dict(params),
        "metadata": {},
    }
    return cmadaas.associate(contract, params, response, request_index=0)


def table():
    return {
        "id": "SYNTHETIC.layers",
        "key_kind": "level_type_and_level",
        "rows": [
            {
                "id": "a",
                "native": {"level_type": "TYPE", "level": "1000.0"},
                "canonical": {"level_type": "pressure", "level": 1000},
            },
            {
                "id": "b",
                "native": {"level_type": "OTHER", "level": "1000.0"},
                "canonical": {"level_type": "height_above_ground", "level": 2},
            },
        ],
    }


def test_service_joint_layer_key_preserves_text_and_pairing(contract):
    record = call(contract)
    value, basis = cmadaas.vertical_table(record, table())
    assert value["level_type"] == "pressure" and basis["rows"] == ["a"]
    assert basis["roles"]["level"] == "request_association"
    assert (
        len(
            cmadaas.vertical_candidates(
                {"level_type": "pressure", "level": 1000}, table()
            )
        )
        == 1
    )
    with pytest.raises(SourceError) as exc:
        cmadaas.vertical_table(call(contract, fcstLevel="1000"), table())
    assert exc.value.context["reason"] == "unmapped_native_value"


def test_call_snapshot_conflicts_and_truncation(contract):
    record = call(contract)
    params = dict(record.parameters)
    params["time"] = "changed"
    assert record.parameters["time"] == "20260101080000"
    bad = deepcopy(record.response)
    bad["metadata"]["fcstLevel"] = "1000"
    conflict = cmadaas.associate(
        contract, dict(record.parameters), bad, request_index=1
    )
    with pytest.raises(SourceError) as exc:
        cmadaas.vertical_table(conflict, table())
    assert exc.value.context["reason"] == "inconsistent_native_metadata"
    bad = deepcopy(record.response)
    bad["truncated"] = True
    with pytest.raises(SourceError) as exc:
        cmadaas.associate(contract, dict(record.parameters), bad, request_index=1)
    assert exc.value.code == "incomplete_response"


def test_service_timezone_and_step_not_guessed(contract):
    record = call(contract)
    identity, origins = cmadaas.time_fields(record, "Asia/Shanghai")
    assert (
        identity["time"] == "2026-01-01T00:00:00Z" and identity["step"] == "PT172800S"
    )
    assert origins["valid_time"] == ["request_association", "request_association"]
    assert cmadaas.encode_time(identity, "Asia/Shanghai") == {
        "time": "20260101080000",
        "step": "48",
    }
    with pytest.raises(QueryError):
        cmadaas.encode_time(
            {"time": identity["time"], "step": "PT30M"}, "Asia/Shanghai"
        )
    with pytest.raises(QueryError):
        cmadaas.time_fields(record, None)
    params = {k: v for k, v in record.parameters.items() if k != "validTime"}
    response = {**record.response, "request_parameters": params}
    analysis = cmadaas.associate(contract, params, response, request_index=1)
    with pytest.raises(QueryError):
        cmadaas.time_fields(analysis, "Asia/Shanghai")
    assert (
        cmadaas.time_fields(analysis, "Asia/Shanghai", fixed_step="PT0H")[0]["step"]
        == "PT0S"
    )


def test_service_numbering_table_and_statistics_definition(contract):
    record = call(contract, fcstMember="MEMBER_A")
    config = SimpleNamespace(member_role=lambda n: "perturbation" if n else "control")
    members = {
        "id": "SYNTHETIC.members",
        "rows": [
            {"id": "m", "native": {"code": "MEMBER_A"}, "canonical": {"member": 2}}
        ],
    }
    assert cmadaas.member_field(record, config, members)[0] == {
        "member": 2,
        "member_role": "perturbation",
    }
    identity, _ = cmadaas.time_fields(record, "Asia/Shanghai")
    stats = {
        "statistics": {
            "over": "time",
            "operation": "accumulation",
            "period": {"kind": "trailing", "duration": "PT24H"},
        }
    }
    _, window, basis = cmadaas.statistics_fields(record, stats, identity)
    assert window == {"start": "2026-01-02T00:00:00Z", "end": "2026-01-03T00:00:00Z"}
    assert basis["statistics"] == "definition"
    with pytest.raises(QueryError):
        cmadaas.statistics_fields(record, {}, identity)


def test_ensemble_mean_probability_and_fixed_event_comparison(native):
    resources = SimpleNamespace(
        parameter=lambda name: {
            "fixed_conditions": {
                "statistics": {"over": "time", "operation": "instantaneous"}
            }
        }
    )
    product = {"populations": [{"id": "all", "members": [0, 1, 2]}]}
    context = dict(
        of={"parameter_id": "SYNTHETIC.t"}, population={"ref": "all"}, over="ensemble"
    )
    record = {**native, "productDefinitionTemplateNumber": 2, "derivedForecast": 0}
    identity, _ = grib.time_fields(record)
    mean = {**context, "operation": "mean", "method": {"weighting": "equal"}}
    assert (
        grib.statistics(
            record,
            {"statistics": mean},
            identity,
            None,
            resources=resources,
            product=product,
        )
        == mean
    )
    event = {"operator": "gt", "threshold": {"value": -5, "unit": "m/s"}}
    probability = {
        **context,
        "operation": "probability",
        "event": event,
        "method": {"kind": "member_fraction", "denominator": "expected_members"},
    }
    record = {
        **native,
        "productDefinitionTemplateNumber": 5,
        "probabilityType": 3,
        "scaleFactorOfLowerLimit": 0,
        "scaledValueOfLowerLimit": -5,
    }
    assert (
        grib.statistics(
            record,
            {"statistics": probability},
            identity,
            None,
            resources=resources,
            product=product,
            object_unit="m/s",
        )
        == probability
    )
    with pytest.raises(SourceError) as exc:
        grib.statistics(
            record,
            {"statistics": {**probability, "event": {**event, "operator": "ge"}}},
            identity,
            None,
            resources=resources,
            product=product,
            object_unit="m/s",
        )
    assert exc.value.context["reason"] == "fixed_definition_mismatch"


def test_unregistered_profile_and_missing_fixed_surface_are_not_damage(native):
    with pytest.raises(SourceError) as exc:
        grib.time_fields({**native, "tablesVersion": 15})
    assert exc.value.context["reason"] == "unsupported_native_encoding"
    with pytest.raises(SourceError) as exc:
        grib.fixed_surfaces({**native, "typeOfFirstFixedSurface": 255})
    assert exc.value.context["reason"] == "missing_native_metadata"


def test_probability_interval_retains_endpoint_inclusion_and_signed_limits(native):
    resources = SimpleNamespace(
        parameter=lambda name: {
            "fixed_conditions": {
                "statistics": {"over": "time", "operation": "instantaneous"}
            }
        }
    )
    product = {"populations": [{"id": "all", "members": [0, 1, 2]}]}
    record = {
        **native,
        "productDefinitionTemplateNumber": 5,
        "probabilityType": 2,
        "scaleFactorOfLowerLimit": 0,
        "scaledValueOfLowerLimit": -5,
        "scaleFactorOfUpperLimit": 0,
        "scaledValueOfUpperLimit": 10,
    }
    identity, _ = grib.time_fields(record)
    event = {
        "operator": "between",
        "lower": {"value": -5, "unit": "m/s", "inclusive": True},
        "upper": {"value": 10, "unit": "m/s", "inclusive": False},
    }
    stats = {
        "over": "ensemble",
        "operation": "probability",
        "of": {"parameter_id": "SYNTHETIC.u"},
        "population": {"ref": "all"},
        "method": {"kind": "member_fraction", "denominator": "expected_members"},
        "event": event,
    }
    assert (
        grib.statistics(
            record,
            {"statistics": stats},
            identity,
            None,
            resources=resources,
            product=product,
            object_unit="m/s",
        )
        == stats
    )
    with pytest.raises(SourceError) as exc:
        grib.statistics(
            {**record, "probabilityType": 5},
            {"statistics": stats},
            identity,
            None,
            resources=resources,
            product=product,
            object_unit="m/s",
        )
    assert (
        exc.value.context["reason"] == "unsupported_native_encoding"
    )  # Equality events are outside the confirmed Query/resource vocabulary.


def test_response_fact_origins_do_not_claim_request_independence(contract):
    record = call(contract)
    record.response["metadata"].update(
        time=record.parameters["time"], validTime=record.parameters["validTime"]
    )
    identity, origins = cmadaas.time_fields(record, "Asia/Shanghai")
    assert origins["time"] == origins["step"] == "response"
    stats = {
        "statistics": {
            "over": "time",
            "operation": "accumulation",
            "period": {"kind": "trailing", "duration": "PT24H"},
        }
    }
    _, _, origins = cmadaas.statistics_fields(record, stats, identity)
    assert origins["interval"] == ["definition", "response"]


def test_ensemble_object_omission_never_defaults_to_instantaneous(native):
    record = {**native, "productDefinitionTemplateNumber": 2, "derivedForecast": 0}
    identity, _ = grib.time_fields(record)
    stats = {
        "over": "ensemble",
        "operation": "mean",
        "of": {"parameter_id": "SYNTHETIC.t"},
        "population": {"ref": "all"},
        "method": {"weighting": "equal"},
    }
    with pytest.raises(QueryError) as exc:
        grib.statistics(
            record,
            {"statistics": stats},
            identity,
            None,
            resources=SimpleNamespace(parameter=lambda name: {"fixed_conditions": {}}),
            product={"populations": [{"id": "all", "members": [0, 1, 2]}]},
        )
    assert exc.value.context["reason"] == "missing_context"
    assert exc.value.path == "/statistics/of"
