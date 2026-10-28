"""Independent SYNTHETIC expectations for observed native encoding boundaries."""

from types import SimpleNamespace

import pytest

from cedarkit_query import SourceError, QueryError
from reki.translation import grib
from reki.translation.grib_backend import GribScan


@pytest.fixture
def native():
    return dict(
        edition=2,
        centre=38,
        subCentre=0,
        tablesVersion=4,
        localTablesVersion=0,
        productDefinitionTemplateNumber=8,
        significanceOfReferenceTime=0,
        year=2026,
        month=1,
        day=1,
        hour=0,
        minute=0,
        second=0,
        indicatorOfUnitOfTimeRange=1,
        forecastTime=-1,
        numberOfTimeRange=1,
        typeOfTimeIncrement=2,
        indicatorOfUnitForTimeRange=1,
        lengthOfTimeRange=1,
        typeOfStatisticalProcessing=1,
        yearOfEndOfOverallTimeInterval=2026,
        monthOfEndOfOverallTimeInterval=1,
        dayOfEndOfOverallTimeInterval=1,
        hourOfEndOfOverallTimeInterval=0,
        minuteOfEndOfOverallTimeInterval=0,
        secondOfEndOfOverallTimeInterval=0,
        typeOfFirstFixedSurface=1,
        typeOfSecondFixedSurface=8,
    )


@pytest.mark.parametrize("template", [8, 9, 10, 11, 12])
def test_signed_interval_start_keeps_reference_and_result_time(native, template):
    identity, interval = grib.time_fields(
        {**native, "productDefinitionTemplateNumber": template}
    )
    assert identity == {
        "time": "2026-01-01T00:00:00Z",
        "step": "PT0S",
        "valid_time": "2026-01-01T00:00:00Z",
    }
    assert interval == {"start": "2025-12-31T23:00:00Z", "end": "2026-01-01T00:00:00Z"}
    stats = {
        "over": "time",
        "operation": "sum",
        "period": {"kind": "trailing", "duration": "PT1H"},
    }
    grib.check_period(stats, identity, interval)
    with pytest.raises(SourceError) as exc:
        grib.check_period(
            {**stats, "period": {"kind": "since_initialization"}}, identity, interval
        )
    assert exc.value.context["reason"] == "fixed_definition_mismatch"


@pytest.mark.parametrize("template", [0, 1, 2, 5, 6])
def test_negative_instant_result_stays_explicitly_unsupported(native, template):
    with pytest.raises(SourceError) as exc:
        grib.time_fields({**native, "productDefinitionTemplateNumber": template})
    assert exc.value.context["reason"] == "unsupported_native_encoding"


def test_interval_before_reference_and_bad_length_are_distinct(native):
    before = {
        **native,
        "forecastTime": -2,
        "yearOfEndOfOverallTimeInterval": 2025,
        "monthOfEndOfOverallTimeInterval": 12,
        "dayOfEndOfOverallTimeInterval": 31,
        "hourOfEndOfOverallTimeInterval": 23,
    }
    with pytest.raises(SourceError) as exc:
        grib.time_fields(before)
    assert exc.value.context["reason"] == "unsupported_native_encoding"
    with pytest.raises(SourceError) as exc:
        grib.time_fields({**native, "lengthOfTimeRange": 2})
    assert exc.value.context["reason"] == "inconsistent_native_metadata"


def test_zero_width_time_encoding_is_neither_instant_nor_an_invented_period(native):
    record = {**native, "forecastTime": 0, "lengthOfTimeRange": 0}
    identity, interval = grib.time_fields(record)
    assert interval["start"] == interval["end"] == "2026-01-01T00:00:00Z"
    assert identity["step"] == "PT0S"
    with pytest.raises(QueryError) as exc:
        grib.statistics(record, {}, identity, interval)
    assert exc.value.context["reason"] == "missing_context"
    with pytest.raises(SourceError) as exc:
        grib.statistics(
            record,
            {"statistics": {"over": "time", "operation": "instantaneous"}},
            identity,
            interval,
        )
    assert exc.value.context["reason"] == "fixed_definition_mismatch"


@pytest.mark.parametrize("first,second", [(1, 8), (8, 1)])
def test_ground_to_nominal_top_is_a_named_layer_in_both_encoded_orders(
    native, first, second
):
    result = grib.fixed_surfaces(
        {**native, "typeOfFirstFixedSurface": first, "typeOfSecondFixedSurface": second}
    )
    assert result == {
        "layer": {"bottom": {"type": "surface"}, "top": {"type": "atmosphere_top"}}
    }


def test_other_named_pairs_do_not_gain_unproven_meaning(native):
    with pytest.raises(SourceError) as exc:
        grib.fixed_surfaces({**native, "typeOfFirstFixedSurface": 10})
    assert exc.value.context["reason"] == "unsupported_native_encoding"
    assert grib.fixed_surfaces(
        {**native, "typeOfFirstFixedSurface": 10, "typeOfSecondFixedSurface": 255}
    ) == {"level_type": "entire_atmosphere"}


@pytest.mark.parametrize("literal", [None, "", "unknown", "~"])
@pytest.mark.parametrize("declared", [False, True])
def test_grib_placeholder_unit_requires_independent_source_evidence(
    native, literal, declared
):
    parameter = {
        "parameter_id": "SYNTHETIC.t",
        "name": "t",
        "unit": "K",
        "fixed_conditions": {},
    }
    backend = SimpleNamespace(
        configuration=SimpleNamespace(
            resources=SimpleNamespace(parameter=lambda name: parameter), product=None
        ),
        vertical_definition=None,
        quantity_kinds={},
    )
    run = object.__new__(GribScan)
    run.backend = backend
    mapping = {
        "parameter_id": "SYNTHETIC.t",
        "native": {
            "translate": {
                "unit": {
                    "rule": "common.value_unit",
                    **({"config": {"source_unit": "K"}} if declared else {}),
                }
            }
        },
    }
    metadata = {**native, "productDefinitionTemplateNumber": 0, "units": literal}
    if declared:
        _, requirements = run._interpret({}, metadata, mapping, None)
        assert requirements["source_unit"] == requirements["unit"] == "K"
    else:
        with pytest.raises(SourceError) as exc:
            run._interpret({}, metadata, mapping, None)
        assert exc.value.context["reason"] == "missing_native_metadata"
    assert grib.source_value_unit(metadata) is None


def test_unit_conflict_is_not_hidden_and_opaque_literal_is_not_rewritten(native):
    from reki.translation.common import value_unit

    assert grib.source_value_unit({"units": "kg m**-2"}) == "kg m**-2"
    with pytest.raises(SourceError) as exc:
        value_unit(
            "degC",
            "K",
            {"rule": "common.value_unit", "config": {"source_unit": "K"}},
            quantity_kind="absolute_temperature",
        )
    assert exc.value.context["reason"] == "inconsistent_native_metadata"


@pytest.fixture
def grid():
    return {
        "gridType": "regular_ll",
        "Ni": 3,
        "Nj": 2,
        "numberOfDataPoints": 6,
        "jPointsAreConsecutive": 0,
        "alternativeRowScanning": 0,
    }


def test_grid_structure_is_scalar_only_and_does_not_invent_endpoint_tolerance(grid):
    assert grib.grid_structure({**grid, "latitudeOfLastGridPoint": 99999999}) == {
        "type": "regular_ll",
        "Ni": 3,
        "Nj": 2,
    }


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"Ni": 0}, "inconsistent_native_metadata"),
        ({"numberOfDataPoints": 5}, "inconsistent_native_metadata"),
        ({"Ni": None}, "missing_native_metadata"),
        ({"Ni": True}, "inconsistent_native_metadata"),
        ({"gridType": "reduced_gg"}, "unsupported_native_encoding"),
        ({"jPointsAreConsecutive": 1}, "unsupported_native_encoding"),
        ({"alternativeRowScanning": 1}, "unsupported_native_encoding"),
    ],
)
def test_grid_structure_diagnostics_remain_explicit(grid, change, reason):
    with pytest.raises(SourceError) as exc:
        grib.grid_structure({**grid, **change})
    assert exc.value.context["reason"] == reason


@pytest.mark.parametrize("missing_dimension", [False, True])
def test_backend_rejects_unregistered_or_missing_grid_metadata_before_arrays(
    monkeypatch, missing_dimension
):
    import eccodes
    from reki.translation.grib_backend import _grid

    handle = eccodes.codes_grib_new_from_samples("regular_ll_sfc_grib2")
    try:
        if missing_dimension:
            defined = eccodes.codes_is_defined
            monkeypatch.setattr(
                eccodes,
                "codes_is_defined",
                lambda h, key: False if key == "Ni" else defined(h, key),
            )
        else:
            eccodes.codes_set_long(handle, "gridDefinitionTemplateNumber", 30)

        def forbidden(*args):
            raise AssertionError("invalid grid requested coordinate arrays")

        monkeypatch.setattr(eccodes, "codes_get_double_array", forbidden)
        with pytest.raises(SourceError) as exc:
            _grid(handle)
        assert exc.value.context["reason"] == (
            "missing_native_metadata"
            if missing_dimension
            else "unsupported_native_encoding"
        )
    finally:
        eccodes.codes_release(handle)
