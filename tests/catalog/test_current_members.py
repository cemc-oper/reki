"""Current GEPS/REPS member bindings with disposable encoded messages."""

import json

import eccodes
import numpy as np
import pytest

from cedarkit_query import QueryError, SourceError, CompletenessError
from reki import from_source
from reki.catalog import load_catalog
from reki.catalog.current import current_member_numbering
from reki.selection.files import _template_values


def encoded(path, member, step, *, level=2, values=None, **overrides):
    path.parent.mkdir(parents=True, exist_ok=True)
    h = eccodes.codes_grib_new_from_samples("regular_ll_sfc_grib2")
    try:
        native = dict(
            Ni=2,
            Nj=2,
            latitudeOfFirstGridPointInDegrees=50,
            latitudeOfLastGridPointInDegrees=49,
            longitudeOfFirstGridPointInDegrees=100,
            longitudeOfLastGridPointInDegrees=101,
            iDirectionIncrementInDegrees=1,
            jDirectionIncrementInDegrees=1,
            centre=38,
            subCentre=0,
            tablesVersion=4,
            localTablesVersion=0,
            productionStatusOfProcessedData=0,
            productDefinitionTemplateNumber=1,
            typeOfProcessedData=3 if member == 0 else 4,
            typeOfGeneratingProcess=4,
            significanceOfReferenceTime=0 if step == 0 else 1,
            typeOfEnsembleForecast=0 if member == 0 else 3 if member % 2 else 2,
            perturbationNumber=member,
            numberOfForecastsInEnsemble=0 if "REPS" in str(path) else 31,
            discipline=0,
            parameterCategory=0,
            parameterNumber=0,
            typeOfFirstFixedSurface=103,
            scaleFactorOfFirstFixedSurface=0,
            scaledValueOfFirstFixedSurface=level,
            typeOfSecondFixedSurface=255,
            dataDate=20261029,
            dataTime=1800,
            indicatorOfUnitOfTimeRange=1,
            forecastTime=step,
        )
        native.update(overrides)
        if native["productDefinitionTemplateNumber"] == 0:
            for key in [
                "typeOfEnsembleForecast",
                "perturbationNumber",
                "numberOfForecastsInEnsemble",
            ]:
                native.pop(key)
        for k, v in native.items():
            eccodes.codes_set(h, k, v)
        eccodes.codes_set_values(
            h, [280 + member + step] * 4 if values is None else values
        )
        with path.open("wb") as stream:
            eccodes.codes_write(h, stream)
    finally:
        eccodes.codes_release(h)


def path_for(root, system, member, step):
    if system == "GEPS":
        return (
            root
            / f"DATA/NAFP/NMC/GRAPES-GEPS/2026/20261029/Z_NAFP_C_BABJ_20261029180000_P_NWPC-GRAPES-GEPS-GLB-{step:03}00-m{member:03}.grib2"
        )
    return (
        root
        / f"ORIG-DATA/NAFP/CMA-REPS/2026/20261030/Z_NAFP_C_BABJ_20261029180000_P_NWPC-GRAPES-REPS-CN-{step:03}00-m{member:03}.grib2"
    )


@pytest.mark.parametrize("system,maximum", [("GEPS", 30), ("REPS", 14)])
@pytest.mark.parametrize("step", [0, 6, 24])
def test_public_member_source_assembly_roles_and_unknown_completeness(
    tmp_path, system, maximum, step
):
    members = [0, 1, 2, maximum]
    for member in members:
        encoded(path_for(tmp_path, system, member, step), member, step)
    with from_source(
        {"kind": "local", "dataset": "CMA-" + system, "root": str(tmp_path)}
    ) as source:
        selected = source.sel(
            parameter="t2m",
            time="2026-10-29T18:00:00Z",
            step=f"PT{step}H",
            member=members,
        )
        explanation = selected.explain()
        assert explanation.context["source"]["product_version"] == "current"
        fields = selected.all()
        assert len(fields) == 4
        ds = fields.to_xarray()
        np.testing.assert_array_equal(ds.member.values, members)
        assert list(ds.member_role.values) == [
            "control",
            "perturbation",
            "perturbation",
            "perturbation",
        ]
        for member in members:
            np.testing.assert_array_equal(
                ds.t2m.sel(member=member).values.reshape(2, 2),
                np.full((2, 2), 280 + member + step),
            )
        one = source.sel(
            parameter="t2m",
            time="2026-10-29T18:00:00Z",
            step=f"PT{step}H",
            member_role="control",
        ).one()
        assert one.identity.to_dict()["member"] == 0
        assert one.to_xarray().t2m.attrs["units"] == "K"
        with pytest.raises(CompletenessError):
            selected.all(completeness="required")


@pytest.mark.parametrize("system,maximum", [("GEPS", 30), ("REPS", 14)])
def test_member_bounds_and_no_statistics_or_unverified_parameters(
    tmp_path, system, maximum
):
    (tmp_path / "unopened").touch()
    with from_source(
        {"kind": "file", "dataset": "CMA-" + system, "path": str(tmp_path / "unopened")}
    ) as source:
        for q in [
            {"member": maximum + 1},
            {"member": 1, "member_role": "control"},
            {"step": "PT12H"},
            {"level_type": "pressure", "level": 700},
            {"statistics": {"over": "ensemble", "operation": "mean"}},
        ]:
            with pytest.raises(QueryError):
                source.sel(parameter="t", **q).explain()
        assert source.sel(parameter="t2m", member_role="perturbation").explain()
        if system == "REPS":
            for name in ["q", "ps"]:
                with pytest.raises(QueryError):
                    source.sel(parameter=name).explain()


@pytest.mark.parametrize("system", ["GEPS", "REPS"])
@pytest.mark.parametrize(
    "native",
    [
        {"typeOfEnsembleForecast": 2, "perturbationNumber": 1},
        {"typeOfEnsembleForecast": 0, "perturbationNumber": 1},
    ],
)
def test_wrong_joint_kind_number_is_not_silently_renumbered(tmp_path, system, native):
    path = path_for(tmp_path, system, 1, 6)
    encoded(path, 1, 6, **native)
    with from_source(
        {"kind": "file", "dataset": "CMA-" + system, "path": str(path)}
    ) as source:
        with pytest.raises((SourceError, QueryError)) as error:
            source.sel(parameter="t2m", member=1, step="PT6H").one()
        assert error.value.code in {"metadata_interpretation_failed", "no_match"}
        if error.value.code == "metadata_interpretation_failed":
            assert error.value.context["reason"] == "unmapped_native_value"


@pytest.mark.parametrize(
    "native",
    [
        {"typeOfGeneratingProcess": 2},
        {"significanceOfReferenceTime": 0},
        {"productDefinitionTemplateNumber": 0},
        {"numberOfForecastsInEnsemble": 15},
    ],
)
def test_wrong_context_does_not_enter_current_member_path(tmp_path, native):
    path = path_for(tmp_path, "GEPS", 1, 6)
    encoded(path, 1, 6, **native)
    with from_source(
        {"kind": "file", "dataset": "CMA-GEPS", "path": str(path)}
    ) as source:
        with pytest.raises((SourceError, QueryError)) as error:
            source.sel(parameter="t2m", member=1, step="PT6H").one()
        assert error.value.code == "no_match"


def test_external_catalog_does_not_inherit_builtin_numbering(tmp_path):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(load_catalog().to_dict()))
    parameters = {"builtin": "reki.parameters.cma-geps.current"}
    from reki.catalog import plan_source_binding

    config = plan_source_binding(
        {"kind": "file", "dataset": "CMA-GEPS", "path": "unopened"},
        product="orig",
        product_version="current",
        context={"catalog": {"path": str(path)}, "parameter_registry": parameters},
    )
    assert current_member_numbering(config) is None


@pytest.mark.parametrize(
    "time,date,year",
    [
        ("2026-10-29T06:00:00Z", "20261029", "2026"),
        ("2026-10-29T18:00:00Z", "20261030", "2026"),
        ("2026-12-31T18:00:00Z", "20270101", "2027"),
    ],
)
def test_reps_directory_date_changes_without_changing_utc_filename(time, date, year):
    values = _template_values(
        "{beijing_year}/{beijing_date_label}/{start_time_label}", {"time": time}
    )
    assert values["beijing_date_label"] == date and values["beijing_year"] == year
    assert values["start_time_label"] == time[:13].replace("-", "").replace("T", "")


def accumulated(path, member, step, **overrides):
    from datetime import datetime, timedelta

    end = datetime(2026, 10, 29, 18) + timedelta(hours=step)
    native = dict(
        productDefinitionTemplateNumber=11,
        parameterCategory=1,
        parameterNumber=8,
        typeOfFirstFixedSurface=1,
        forecastTime=0,
        numberOfTimeRange=1,
        typeOfStatisticalProcessing=1,
        typeOfTimeIncrement=2,
        indicatorOfUnitForTimeRange=1,
        lengthOfTimeRange=step,
        yearOfEndOfOverallTimeInterval=end.year,
        monthOfEndOfOverallTimeInterval=end.month,
        dayOfEndOfOverallTimeInterval=end.day,
        hourOfEndOfOverallTimeInterval=end.hour,
        minuteOfEndOfOverallTimeInterval=0,
        secondOfEndOfOverallTimeInterval=0,
        values=[0 if step == 0 else 6.25 + member] * 4,
    )
    native.update(overrides)
    encoded(path, member, step, **native)


@pytest.mark.parametrize("system", ["GEPS", "REPS"])
@pytest.mark.parametrize("step", [0, 6, 24])
def test_current_accumulation_keeps_member_interval_and_distinct_source_unit(
    tmp_path, system, step
):
    for member in [0, 1, 2]:
        accumulated(path_for(tmp_path, system, member, step), member, step)
    with from_source(
        {"kind": "local", "dataset": "CMA-" + system, "root": str(tmp_path)}
    ) as source:
        query = source.sel(
            parameter="rain",
            time="2026-10-29T18:00:00Z",
            step=f"PT{step}H",
            member=[0, 1, 2],
        )
        fields = query.all()
        ds = fields.to_xarray()
        assert len(fields) == 3 and ds.rain.attrs["units"] == "mm"
        for field in fields:
            identity = field.identity.to_dict()
            meta = field.metadata
            assert identity["parameter"] == "cedarkit.rain.since-initialization"
            assert identity["step"] == f"PT{step * 3600}S"
            assert meta["source_unit"] == "kg/m2" and meta["unit"] == "mm"
            assert meta["statistics"]["period"] == {"kind": "since_initialization"}
            assert meta["statistical_interval"]["start"] == identity["time"]
            assert meta["statistical_interval"]["end"] == identity["valid_time"]
            assert meta["native_fields"]["forecastTime"] == 0
            assert meta["quantity_kind"] == "water_equivalent_precipitation"
            expected = 0 if step == 0 else 6.25 + identity["member"]
            np.testing.assert_array_equal(
                ds.rain.sel(member=identity["member"]).values.reshape(2, 2),
                np.full((2, 2), expected),
            )
        alias = source.sel(
            parameter="APCP",
            time="2026-10-29T18:00:00Z",
            step=f"PT{step}H",
            member_role="control",
        ).one()
        assert (
            alias.identity.to_dict()["parameter"]
            == "cedarkit.rain.since-initialization"
        )
        assert (
            "period"
            not in source.configuration.resources.parameter("cedarkit.rain")[
                "fixed_conditions"
            ]["statistics"]
        )
        with pytest.raises(QueryError):
            source.sel(parameter="cedarkit.rain").explain()
        with pytest.raises(CompletenessError):
            query.all(completeness="required")


@pytest.mark.parametrize(
    "native,reason",
    [
        ({"forecastTime": 18, "lengthOfTimeRange": 6}, "fixed_definition_mismatch"),
        ({"lengthOfTimeRange": 6}, "inconsistent_native_metadata"),
        ({"hourOfEndOfOverallTimeInterval": 17}, "inconsistent_native_metadata"),
    ],
)
def test_member_accumulation_rejects_reanchored_or_inconsistent_interval(
    tmp_path, native, reason
):
    path = path_for(tmp_path, "GEPS", 1, 24)
    accumulated(path, 1, 24, **native)
    with from_source(
        {"kind": "file", "dataset": "CMA-GEPS", "path": str(path)}
    ) as source:
        with pytest.raises(SourceError) as error:
            source.sel(parameter="rain", member=1, step="PT24H").one()
        assert error.value.code == "metadata_interpretation_failed"
        assert error.value.context["reason"] == reason


@pytest.mark.parametrize(
    "native",
    [
        {"numberOfTimeRange": 2},
        {"typeOfTimeIncrement": 1},
        {"typeOfStatisticalProcessing": 0},
        {"productDefinitionTemplateNumber": 1},
    ],
)
def test_unregistered_statistical_context_is_not_accepted(tmp_path, native):
    # A deterministic instantaneous record cannot enter an accumulation mapping.
    path = path_for(tmp_path, "GEPS", 0, 6)
    if native.get("productDefinitionTemplateNumber") == 1:
        encoded(
            path,
            0,
            6,
            parameterCategory=1,
            parameterNumber=8,
            typeOfFirstFixedSurface=1,
        )
    else:
        accumulated(path, 0, 6, **native)
    with from_source(
        {"kind": "file", "dataset": "CMA-GEPS", "path": str(path)}
    ) as source:
        if native.get("productDefinitionTemplateNumber") == 1:
            with pytest.raises(QueryError) as error:
                source.sel(parameter="rain", member=0, step="PT6H").one()
            assert error.value.code == "no_match"
        else:
            with pytest.raises(SourceError) as error:
                source.sel(parameter="rain", member=0, step="PT6H").one()
            assert error.value.context["reason"] == (
                "fixed_definition_mismatch"
                if native.get("typeOfStatisticalProcessing") == 0
                else "unsupported_native_encoding"
            )


@pytest.mark.parametrize(
    "patch",
    [
        {"units": "K"},
        {"parameterUnits": "K"},
        {"units": "kg m**-2", "parameterUnits": "mm"},
    ],
)
def test_precipitation_source_unit_conflicts_are_not_overridden(
    tmp_path, monkeypatch, patch
):
    from reki.translation import grib_backend

    path = path_for(tmp_path, "GEPS", 0, 6)
    accumulated(path, 0, 6)
    original = grib_backend._metadata

    def conflict(*args, **kwargs):
        result = original(*args, **kwargs)
        if result.get("productDefinitionTemplateNumber") == 11:
            result.update(patch)
        return result

    monkeypatch.setattr(grib_backend, "_metadata", conflict)
    with from_source(
        {"kind": "file", "dataset": "CMA-GEPS", "path": str(path)}
    ) as source:
        with pytest.raises(SourceError) as error:
            source.sel(parameter="rain", member=0, step="PT6H").one()
        assert error.value.context["reason"] == "inconsistent_native_metadata"


def test_water_equivalent_conversion_requires_specific_quantity_evidence():
    from decimal import Decimal
    from reki.translation.common import value_unit

    with pytest.raises(QueryError):
        value_unit("kg/m2", "mm")
    with pytest.raises(QueryError):
        value_unit("kg/m2", "mm", quantity_kind="absolute_temperature")
    with pytest.raises(QueryError):
        value_unit("kg/m2/s", "mm", quantity_kind="water_equivalent_precipitation")
    requirement = value_unit(
        "kg m**-2", "mm", quantity_kind="water_equivalent_precipitation"
    )
    assert (
        requirement.source,
        requirement.target,
        requirement.scale,
        requirement.offset,
    ) == ("kg/m2", "mm", Decimal(1), Decimal(0))


def test_precipitation_bitmap_survives_water_equivalent_output(tmp_path):
    path = path_for(tmp_path, "REPS", 0, 6)
    accumulated(
        path, 0, 6, values=[0, 9999, 1.25, 2.5], bitmapPresent=1, missingValue=9999
    )
    with from_source(
        {"kind": "file", "dataset": "CMA-REPS", "path": str(path)}
    ) as source:
        values = (
            source.sel(parameter="rain", member=0, step="PT6H")
            .one()
            .to_xarray()
            .rain.values.reshape(2, 2)
        )
        np.testing.assert_allclose(
            values, [[0, np.nan], [1.25, 2.5]], rtol=0, atol=0, equal_nan=True
        )
