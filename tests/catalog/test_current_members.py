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


def encoded(path, member, step, *, level=2, **overrides):
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
        eccodes.codes_set_values(h, [280 + member + step] * 4)
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
