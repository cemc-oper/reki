"""Generated ensemble products with explicit SYNTHETIC population/method evidence.

These cases verify interpretation, not GEPS/REPS product availability or methods.
No individual member fields are created or recomputed.
"""

import json
from copy import deepcopy
from types import SimpleNamespace

import eccodes
import numpy as np
import pytest

from cedarkit_query import QueryError, SourceError
from reki.catalog import plan_source_binding
from reki.catalog.model import thaw
from reki.selection.core import construct_source
from reki.translation import grib
from reki.translation.grib_backend import GribBackend


@pytest.fixture
def ensemble():
    native = dict(
        edition=2,
        centre=38,
        subCentre=0,
        tablesVersion=4,
        localTablesVersion=0,
        productDefinitionTemplateNumber=2,
        significanceOfReferenceTime=1,
        year=2026,
        month=10,
        day=30,
        hour=0,
        minute=0,
        second=0,
        forecastTime=6,
        indicatorOfUnitOfTimeRange=1,
        derivedForecast=4,
        numberOfForecastsInEnsemble=3,
    )
    product = {
        "populations": [
            {
                "id": "synthetic.all",
                "members": [0, 1, 2],
                "missing": {"policy": "require_all"},
            }
        ]
    }
    stats = {
        "over": "ensemble",
        "operation": "standard_deviation",
        "of": {"parameter_id": "synthetic.t"},
        "population": {"ref": "synthetic.all"},
        "method": {"weighting": "equal", "ddof": 0},
    }
    resources = SimpleNamespace(
        parameter=lambda name: {
            "fixed_conditions": {
                "statistics": {"over": "time", "operation": "instantaneous"}
            }
        }
    )

    def interpret(*, metadata=None, definition=None, context=None):
        record = native if metadata is None else metadata
        identity, interval = grib.time_fields(record)
        return grib.statistics(
            record,
            {"statistics": stats if definition is None else definition},
            identity,
            interval,
            resources=resources,
            product=product if context is None else context,
        )

    return native, stats, product, interpret


@pytest.mark.parametrize("ddof", [0, 1])
def test_spread_requires_a_concrete_method_without_inventing_ddof(ensemble, ddof):
    _, stats, _, interpret = ensemble
    definition = deepcopy(stats)
    definition["method"]["ddof"] = ddof
    assert interpret(definition=definition) == definition
    del definition["method"]["ddof"]
    with pytest.raises(QueryError) as exc:
        interpret(definition=definition)
    assert exc.value.context["reason"] == "missing_context"


@pytest.mark.parametrize("code", [1, 2, 3, 6, 7, 10, 192])
def test_other_derived_statistics_are_not_all_member_standard_deviation(ensemble, code):
    native, _, _, interpret = ensemble
    with pytest.raises(SourceError) as exc:
        interpret(metadata={**native, "derivedForecast": code})
    assert exc.value.context["reason"] == "unsupported_native_encoding"


@pytest.mark.parametrize("count", [1, 2, 4])
def test_native_count_cannot_override_required_population(ensemble, count):
    native, _, _, interpret = ensemble
    with pytest.raises(SourceError) as exc:
        interpret(metadata={**native, "numberOfForecastsInEnsemble": count})
    assert exc.value.context["reason"] == "fixed_definition_mismatch"


@pytest.mark.parametrize("count", [0, -1, True])
def test_malformed_native_count_is_not_an_unknown_population(ensemble, count):
    native, _, _, interpret = ensemble
    with pytest.raises(SourceError) as exc:
        interpret(metadata={**native, "numberOfForecastsInEnsemble": count})
    assert exc.value.context["reason"] == "invalid_statistics_metadata"


@pytest.mark.parametrize(
    "count,accepted", [(1, False), (2, True), (3, True), (4, False)]
)
def test_available_member_policy_checks_explicit_minimum(ensemble, count, accepted):
    native, _, product, interpret = ensemble
    context = deepcopy(product)
    context["populations"][0].update(
        members={"range": {"start": 0, "end": 2, "every": 1}},
        missing={"policy": "use_available", "min_members": 2},
    )
    metadata = {**native, "numberOfForecastsInEnsemble": count}
    if accepted:
        assert (
            interpret(metadata=metadata, context=context)["operation"]
            == "standard_deviation"
        )
    else:
        with pytest.raises(SourceError) as exc:
            interpret(metadata=metadata, context=context)
        assert exc.value.context["reason"] == "fixed_definition_mismatch"


def test_mean_operation_and_missing_count_still_need_the_declared_context(ensemble):
    native, stats, product, interpret = ensemble
    definition = {**stats, "operation": "mean", "method": {"weighting": "equal"}}
    record = {**native, "derivedForecast": 0}
    del record["numberOfForecastsInEnsemble"]
    assert interpret(metadata=record, definition=definition) == definition
    with pytest.raises(SourceError) as exc:
        interpret(metadata=native, definition=definition)
    assert exc.value.context["reason"] == "fixed_definition_mismatch"
    with pytest.raises(QueryError) as exc:
        interpret(metadata=record, definition=definition, context={"populations": []})
    assert exc.value.context["reason"] == "missing_context"
    assert product["populations"][0]["members"] == [0, 1, 2]


@pytest.mark.parametrize("count", [None, 255])
def test_missing_count_retains_explicit_population_without_inferring_members(
    ensemble, count
):
    native, stats, _, interpret = ensemble
    assert interpret(metadata={**native, "numberOfForecastsInEnsemble": count}) == stats


@pytest.mark.parametrize("template", [2, 12])
@pytest.mark.parametrize("operation,code", [("mean", 0), ("standard_deviation", 4)])
def test_encoded_products_select_and_assemble_without_individual_members(
    tmp_path, ensemble, template, operation, code
):
    _, stats, product, _ = ensemble
    stats = {**stats, "operation": operation}
    if operation == "mean":
        stats["method"] = {"weighting": "equal"}
    object_statistic = {"over": "time", "operation": "instantaneous"}
    if template == 12:
        product["populations"][0]["members"] = {
            "range": {"start": 0, "end": 2, "every": 1}
        }
        object_statistic = {
            "over": "time",
            "operation": "mean",
            "period": {"kind": "trailing", "duration": "PT6H"},
            "method": {"kind": "sample_mean"},
        }
    parameters = {
        "api_version": "cedarkit.parameters/v1",
        "id": "synthetic.parameters",
        "version": "1",
        "parameters": [
            {
                "parameter_id": "synthetic.t",
                "name": "t",
                "unit": "K",
                "fixed_conditions": {"statistics": object_statistic},
            },
            {
                "parameter_id": "synthetic.result",
                "name": "result",
                "unit": "K",
                "fixed_conditions": {"statistics": stats},
            },
        ],
    }
    mappings = {
        "api_version": "cedarkit.mappings/v1",
        "id": "synthetic.mappings",
        "version": "1",
        "backend": "grib2",
        "tables": [],
        "mappings": [
            {
                "id": "result",
                "parameter_id": "synthetic.result",
                "backend": "grib2",
                "applies_to": {},
                "when": {},
                "native": {
                    "match": {
                        "discipline": 0,
                        "parameterCategory": 0,
                        "parameterNumber": 0,
                        "productDefinitionTemplateNumber": template,
                    },
                    "translate": {
                        "vertical": {"rule": "grib.fixed_surfaces"},
                        "time": {"rule": "grib.time"},
                        "statistics": {"rule": "grib.statistics"},
                        "unit": {"rule": "common.value_unit"},
                    },
                },
                "evidence": [
                    "SYNTHETIC generated result only; no member recomputation or CMA product claim"
                ],
            }
        ],
    }
    catalog = {
        "api_version": "cedarkit.catalog/v1",
        "id": "synthetic.catalog",
        "version": "1",
        "datasets": [
            {
                "id": "synthetic",
                "aliases": [],
                "mappings": {"grib2": {"path": "mappings.json"}},
                "products": [
                    {
                        "id": "formal",
                        "version": "synthetic-1",
                        "scope": {},
                        "provides": [{"parameter": "synthetic.result"}],
                        "populations": product["populations"],
                        "methods": [],
                        "sources": [{"id": "files", "kind": "file"}],
                        "evidence": ["SYNTHETIC"],
                    }
                ],
            }
        ],
    }
    for name, data in [
        ("parameters", parameters),
        ("mappings", mappings),
        ("catalog", catalog),
    ]:
        (tmp_path / (name + ".json")).write_text(json.dumps(data))
    path = tmp_path / "SYNTHETIC-result.grib2"
    values = np.array([2.0, 3.0, 4.0, 5.0])
    handle = eccodes.codes_grib_new_from_samples("regular_ll_sfc_grib2")
    try:
        settings = {
            "Ni": 2,
            "Nj": 2,
            "latitudeOfFirstGridPointInDegrees": 50,
            "latitudeOfLastGridPointInDegrees": 49,
            "longitudeOfFirstGridPointInDegrees": 100,
            "longitudeOfLastGridPointInDegrees": 101,
            "iDirectionIncrementInDegrees": 1,
            "jDirectionIncrementInDegrees": 1,
            "dataDate": 20261030,
            "dataTime": 0,
            "tablesVersion": 4,
            "productDefinitionTemplateNumber": template,
            "derivedForecast": code,
            "numberOfForecastsInEnsemble": 3,
            "forecastTime": 6 if template == 2 else 0,
        }
        if template == 12:
            settings.update(
                numberOfTimeRange=1,
                typeOfStatisticalProcessing=0,
                typeOfTimeIncrement=2,
                indicatorOfUnitForTimeRange=1,
                lengthOfTimeRange=6,
                yearOfEndOfOverallTimeInterval=2026,
                monthOfEndOfOverallTimeInterval=10,
                dayOfEndOfOverallTimeInterval=30,
                hourOfEndOfOverallTimeInterval=6,
                minuteOfEndOfOverallTimeInterval=0,
                secondOfEndOfOverallTimeInterval=0,
            )
        for key, value in settings.items():
            eccodes.codes_set(handle, key, value)
        eccodes.codes_set_values(handle, values)
        with path.open("wb") as stream:
            eccodes.codes_write(handle, stream)
    finally:
        eccodes.codes_release(handle)
    configuration = plan_source_binding(
        {"kind": "file", "dataset": "synthetic", "path": str(path)},
        context={
            "catalog": {"path": str(tmp_path / "catalog.json")},
            "parameter_registry": {"path": str(tmp_path / "parameters.json")},
        },
        product="formal",
        product_version="synthetic-1",
    )
    with construct_source(configuration, GribBackend(configuration)) as source:
        selected = source.sel(parameter="result")
        field = selected.one()
        assert "member" not in field.identity.to_dict()
        assert "member_role" not in field.identity.to_dict()
        assert thaw(field.metadata["statistics"]) == stats
        array = selected.all().to_xarray()
        assert "member" not in array.dims
        np.testing.assert_array_equal(array.result.values.reshape(-1), values)
        assert array.result.attrs["units"] == "K"
        assert field.identity.to_dict()["step"] == "PT21600S"
        with pytest.raises(QueryError):
            source.sel(parameter="result", member=0)
