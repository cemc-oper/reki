"""SYNTHETIC actual-encoding tests for the five confirmed GRIB template families.

Definitions and complete expected sets are author declarations, independent of
returned records. Built-in ecCodes samples are not CEMC product evidence.
"""

from copy import deepcopy
import json

import eccodes
import numpy as np
import pytest

from cedarkit_query import Query, QueryError, SourceError, normalize_statistics
from cedarkit_query.normalize import duration_seconds
from reki.catalog import plan_source_binding
from reki.selection.core import construct_source
from reki.translation.grib_backend import GribBackend

TEMPLATES = (0, 8, 1, 11, 2, 12, 5, 9, 6, 10)
INTERVAL = {8, 11, 12, 9, 10}
MEMBER = {1, 11}
PROBABILITY = {5, 9}
ENSEMBLE = {2, 12, 5, 9, 6, 10}
REFERENCE = "2026-01-01T00:00:00Z"


def statistics(template):
    obj = {"over": "time", "operation": "instantaneous"}
    if template in INTERVAL:
        obj = {
            "over": "time",
            "operation": "mean",
            "period": {"kind": "trailing", "duration": "PT6H"},
        }
    if template not in ENSEMBLE:
        return obj, obj
    outer = {
        "over": "ensemble",
        "of": {"parameter_id": "synthetic.object"},
        "population": {"ref": "synthetic.all"},
    }
    if template in PROBABILITY:
        outer.update(
            operation="probability",
            event={"operator": "gt", "threshold": {"value": 273.15, "unit": "K"}},
            method={"kind": "member_fraction", "denominator": "expected_members"},
        )
    elif template in {6, 10}:
        outer.update(
            operation="quantile",
            quantile=0.9,
            method={"kind": "empirical_inverse_cdf", "weighting": "equal"},
        )
    else:
        outer.update(operation="mean", method={"weighting": "equal"})
    return outer, obj


def encoded_records(path, template, overrides=(), *, end=12):
    """Encode the independently stated interval and values, not ecCodes step aliases."""
    with path.open("wb") as stream:
        for override in overrides or ({},):
            h = eccodes.codes_grib_new_from_samples("regular_ll_sfc_grib2")
            try:
                settings = {
                    "productDefinitionTemplateNumber": template,
                    "Ni": 2,
                    "Nj": 2,
                    "latitudeOfFirstGridPointInDegrees": 50.0,
                    "latitudeOfLastGridPointInDegrees": 49.0,
                    "longitudeOfFirstGridPointInDegrees": 100.0,
                    "longitudeOfLastGridPointInDegrees": 101.0,
                    "iDirectionIncrementInDegrees": 1.0,
                    "jDirectionIncrementInDegrees": 1.0,
                    "dataDate": 20260101,
                    "dataTime": 0,
                    "forecastTime": 6,
                    "typeOfFirstFixedSurface": 100,
                    "scaleFactorOfFirstFixedSurface": 0,
                    "scaledValueOfFirstFixedSurface": 85000,
                }
                if template in INTERVAL:
                    settings.update(
                        {
                            "numberOfTimeRange": 1,
                            "typeOfTimeIncrement": 2,
                            "typeOfStatisticalProcessing": 0,
                            "indicatorOfUnitForTimeRange": 1,
                            "lengthOfTimeRange": 6,
                            "yearOfEndOfOverallTimeInterval": 2026,
                            "monthOfEndOfOverallTimeInterval": 1,
                            "dayOfEndOfOverallTimeInterval": 1,
                            "hourOfEndOfOverallTimeInterval": end,
                            "minuteOfEndOfOverallTimeInterval": 0,
                            "secondOfEndOfOverallTimeInterval": 0,
                        }
                    )
                if template in MEMBER:
                    settings.update(
                        typeOfEnsembleForecast=3,
                        perturbationNumber=0,
                        numberOfForecastsInEnsemble=2,
                    )
                if template in {2, 12}:
                    settings.update(derivedForecast=0, numberOfForecastsInEnsemble=2)
                if template in PROBABILITY:
                    settings.update(
                        probabilityType=3,
                        scaleFactorOfLowerLimit=2,
                        scaledValueOfLowerLimit=27315,
                    )
                if template in {6, 10}:
                    settings["percentileValue"] = 90
                settings.update({k: v for k, v in override.items() if k != "values"})
                for k, v in settings.items():
                    eccodes.codes_set(h, k, v)
                values = (
                    [25.0, 50.0, 75.0, 100.0]
                    if template in PROBABILITY
                    else [280.0, 281.0, 282.0, 283.0]
                )
                eccodes.codes_set_values(h, override.get("values", values))
                eccodes.codes_write(h, stream)
            finally:
                eccodes.codes_release(h)


@pytest.fixture
def family_source(tmp_path):
    def make(template, *, overrides=(), edit=None, expected=True, layer=False):
        path = tmp_path / "SYNTHETIC.grib2"
        encoded_records(path, template, overrides)
        stats, obj = statistics(template)
        params = dict(
            api_version="cedarkit.parameters/v1",
            id="SYNTHETIC.family.params",
            version="1",
            parameters=[
                dict(
                    parameter_id="synthetic.field",
                    name="field",
                    unit="1" if template in PROBABILITY else "K",
                    fixed_conditions={"statistics": stats},
                ),
                dict(
                    parameter_id="synthetic.object",
                    name="object",
                    unit="K",
                    fixed_conditions={"statistics": obj},
                ),
            ],
        )
        unit = {"rule": "common.value_unit"}
        if template in PROBABILITY:
            # Explicit SYNTHETIC encoding fact, never guessed from the target unit.
            unit["config"] = {"source_unit": "%"}
        maps = dict(
            api_version="cedarkit.mappings/v1",
            id="SYNTHETIC.family.maps",
            version="1",
            backend="grib2",
            tables=[],
            mappings=[
                dict(
                    id="SYNTHETIC.family.field",
                    parameter_id="synthetic.field",
                    backend="grib2",
                    applies_to={
                        "dataset": "SYNTHETIC.family",
                        "product": "SYNTHETIC.p",
                        "product_version": "SYNTHETIC-v1",
                    },
                    when={},
                    native=dict(
                        match={
                            "discipline": 0,
                            "parameterCategory": 0,
                            "parameterNumber": 0,
                            "productDefinitionTemplateNumber": template,
                        },
                        translate={
                            "vertical": {"rule": "grib.fixed_surfaces"},
                            "time": {"rule": "grib.time"},
                            "statistics": {"rule": "grib.statistics"},
                            "unit": unit,
                        },
                    ),
                    evidence=[
                        "SYNTHETIC authored encoding and unit facts; no business product"
                    ],
                )
            ],
        )
        identity = dict(
            parameter="synthetic.field",
            level_type="pressure",
            level=850,
            time=REFERENCE,
            step="PT12H" if template in INTERVAL else "PT6H",
        )
        if layer:
            identity.pop("level")
            identity["layer"] = {"bottom": 850, "top": 500}
        if template in MEMBER:
            identity["member"] = 9
        product = dict(
            id="SYNTHETIC.p",
            version="SYNTHETIC-v1",
            scope={},
            provides=[deepcopy(identity)],
            populations=[
                {
                    "id": "synthetic.all",
                    "members": [4, 9],
                    "missing": {"policy": "use_available", "min_members": 2},
                }
            ],
            methods=[],
            sources=[{"id": "SYNTHETIC.files", "kind": "file"}],
            evidence=[
                "SYNTHETIC independent complete domain; not an observed business domain"
            ],
        )
        catalog = dict(
            api_version="cedarkit.catalog/v1",
            id="SYNTHETIC.family.catalog",
            version="1",
            datasets=[
                dict(
                    id="SYNTHETIC.family",
                    mappings={"grib2": {"path": "maps.json"}},
                    member_roles={"4": "control", "9": "perturbation"},
                    products=[product],
                )
            ],
        )
        if edit:
            edit(params, maps, product)
        for name, value in [("params", params), ("maps", maps), ("catalog", catalog)]:
            (tmp_path / (name + ".json")).write_text(json.dumps(value))
        config = plan_source_binding(
            {"kind": "file", "path": str(path), "dataset": "SYNTHETIC.family"},
            context={
                "catalog": {"path": str(tmp_path / "catalog.json")},
                "parameter_registry": {"path": str(tmp_path / "params.json")},
            },
            product="SYNTHETIC.p",
            product_version="SYNTHETIC-v1",
        )
        backend = GribBackend(
            config,
            numbering={(0, 0): 4, (3, 0): 9},
            expected_domain=[Query(identity)] if expected else None,
            identity_fields=tuple(
                k for k in identity if not (layer and k == "level_type")
            ),
        )
        return construct_source(config, backend), identity, stats

    return make


@pytest.mark.parametrize("template", TEMPLATES)
def test_actual_template_selection_output_and_independent_completeness(
    family_source, template, monkeypatch
):
    source, identity, stats = family_source(template)
    loads = []
    original = eccodes.codes_get_double_array

    def get_array(h, key):
        if key == "values":
            loads.append(key)
        return original(h, key)

    monkeypatch.setattr(eccodes, "codes_get_double_array", get_array)
    with source:
        selection = source.sel(identity)
        assert (
            selection.explain().analysis["translations"][0]["coverage"]["status"]
            == "passed"
        )
        assert not loads
        fields = selection.all(completeness="required")
        assert len(fields) == 1 and not loads
        assert fields.report.overall["status"] == "complete"
        assert fields.report.overall["expected_count"] == 1
        field = fields[0]
        assert field.metadata["statistics"] == normalize_statistics(
            stats, complete=True
        )
        assert duration_seconds(field.identity.step) == (
            43200 if template in INTERVAL else 21600
        )
        assert (
            field.metadata["native_fields"]["productDefinitionTemplateNumber"]
            == template
        )
        assert ("member" in field.identity.to_dict()) == (template in MEMBER)
        if template in MEMBER:
            assert (
                field.identity.member == 9
                and field.identity.member_role == "perturbation"
            )
        if template in INTERVAL:
            assert field.identity.valid_time == "2026-01-01T12:00:00Z"
        ds = fields.to_xarray()
        expected = (
            np.array([[0.25, 0.5], [0.75, 1.0]])
            if template in PROBABILITY
            else np.array([[280.0, 281.0], [282.0, 283.0]])
        )
        np.testing.assert_allclose(
            ds.field.values.reshape(2, 2), expected, rtol=0, atol=0
        )
        np.testing.assert_array_equal(ds.latitude, [50.0, 49.0])
        np.testing.assert_array_equal(ds.longitude, [100.0, 101.0])
        assert ds.field.attrs["units"] == ("1" if template in PROBABILITY else "K")
        assert len(loads) == 1
        assert (
            fields.report.translations[0]["branches"][0]["execution"]["status"]
            == "exhausted"
        )


@pytest.mark.parametrize("template", TEMPLATES)
def test_actual_template_residual_rejects_other_level(family_source, template):
    source, identity, _ = family_source(
        template, overrides=[{}, {"scaledValueOfFirstFixedSurface": 50000}]
    )
    with source:
        fields = source.sel(identity).all(completeness="required")
        assert len(fields) == 1
        assert fields[0].identity.level == 850


@pytest.mark.parametrize(
    "template,patch,reason",
    [
        (8, {"hourOfEndOfOverallTimeInterval": 13}, "inconsistent_native_metadata"),
        (11, {"perturbationNumber": 7}, "unmapped_native_value"),
        (12, {"derivedForecast": 9}, "fixed_definition_mismatch"),
        (5, {"probabilityType": 0}, "fixed_definition_mismatch"),
        (6, {"percentileValue": 101}, "invalid_statistics_metadata"),
    ],
)
def test_actual_template_bad_metadata_never_becomes_missing(
    family_source, template, patch, reason
):
    source, identity, _ = family_source(template, overrides=[patch])
    with source, pytest.raises(SourceError) as exc:
        source.sel(identity).all()
    assert exc.value.context["reason"] == reason


def test_probability_requires_explicit_field_value_unit(family_source):
    def edit(params, maps, product):
        del maps["mappings"][0]["native"]["translate"]["unit"]["config"]

    source, identity, _ = family_source(5, edit=edit)
    with source, pytest.raises(QueryError) as exc:
        source.sel(identity).all()
    assert exc.value.context["reason"] == "missing_context"


@pytest.mark.parametrize("template", sorted(INTERVAL))
def test_interval_end_selects_correct_window_in_actual_stream(family_source, template):
    source, identity, _ = family_source(
        template,
        overrides=[
            {"forecastTime": 0, "hourOfEndOfOverallTimeInterval": 6},
            {},
        ],
    )
    with source:
        fields = source.sel(identity).all(completeness="required")
        assert len(fields) == 1
        assert fields[0].identity.valid_time == "2026-01-01T12:00:00Z"
        assert fields[0].metadata["native_fields"]["forecastTime"] == 6


@pytest.mark.parametrize("template", (1, 11))
def test_equal_native_numbers_keep_distinct_joint_member_identity(
    family_source, template
):
    source, identity, _ = family_source(
        template,
        overrides=[
            {"typeOfEnsembleForecast": 0, "perturbationNumber": 0},
            {"typeOfEnsembleForecast": 3, "perturbationNumber": 0},
        ],
    )
    with source:
        fields = source.sel(identity).all(completeness="required")
        assert len(fields) == 1 and fields[0].identity.member == 9
        assert fields[0].metadata["native_fields"]["typeOfEnsembleForecast"] == 3


@pytest.mark.parametrize("template", TEMPLATES)
def test_actual_layer_boundaries_survive_all_template_families(family_source, template):
    source, identity, _ = family_source(
        template,
        layer=True,
        overrides=[
            {
                "typeOfSecondFixedSurface": 100,
                "scaleFactorOfSecondFixedSurface": 0,
                "scaledValueOfSecondFixedSurface": 50000,
            }
        ],
    )
    with source:
        fields = source.sel(identity).all(completeness="required")
        assert len(fields) == 1
        assert fields[0].identity.layer["bottom"]["value"] == 850
        assert fields[0].identity.layer["top"]["value"] == 500
        ds = fields.to_xarray()
        variable = next(iter(ds.data_vars.values()))
        assert variable.attrs["cedarkit_parameter_id"] == "synthetic.field"
        assert variable.attrs["layer_bottom_value"] == 850
        assert variable.attrs["layer_top_value"] == 500


@pytest.mark.parametrize("template", (8, 11, 12, 9, 10))
def test_actual_trailing_window_cannot_be_relabelled_since_init(
    family_source, template
):
    def edit(params, maps, product):
        parameter = params["parameters"][1 if template in ENSEMBLE else 0]
        parameter["fixed_conditions"]["statistics"].update(
            operation="accumulation", period={"kind": "since_initialization"}
        )

    source, identity, _ = family_source(
        template, edit=edit, overrides=[{"typeOfStatisticalProcessing": 1}]
    )
    with source, pytest.raises(SourceError) as exc:
        source.sel(identity).all()
    assert exc.value.context["reason"] == "fixed_definition_mismatch"


@pytest.mark.parametrize("template", (5, 9))
def test_actual_probability_signed_limits_keep_object_and_field_units_separate(
    family_source, template
):
    def edit(params, maps, product):
        params["parameters"][1]["unit"] = "m/s"
        params["parameters"][0]["fixed_conditions"]["statistics"]["event"][
            "threshold"
        ] = {"value": -5, "unit": "m/s"}
        maps["mappings"][0]["native"]["match"].update(
            parameterCategory=2, parameterNumber=2
        )

    source, identity, _ = family_source(
        template,
        edit=edit,
        overrides=[
            {
                "parameterCategory": 2,
                "parameterNumber": 2,
                "scaleFactorOfLowerLimit": 0,
                "scaledValueOfLowerLimit": -5,
            }
        ],
    )
    with source:
        fields = source.sel(identity).all(completeness="required")
        assert fields[0].metadata["native_fields"]["scaledValueOfLowerLimit"] == -5
        basis = fields[0].metadata["probability_unit_basis"]
        assert basis["field_unit"] == "%"
        assert basis["threshold_unit"] == "m/s"
        assert fields[0].metadata["native_fields"]["parameterUnits"] == "m s-1"
        np.testing.assert_array_equal(
            fields.to_xarray().field.values.reshape(2, 2), [[0.25, 0.5], [0.75, 1.0]]
        )
