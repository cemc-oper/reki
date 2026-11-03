"""Original producer facts with small independently specified encoded fields."""

import json

import eccodes
import numpy as np
import pytest

from cedarkit_query import SourceError
from reki import from_source
from reki.selection.core import matches
from reki.translation import grib
from reki.catalog.model import freeze
from reki.translation.grib_backend import native_matches


def profile(**changes):
    return {
        "edition": 2,
        "centre": 38,
        "subCentre": 0,
        "tablesVersion": 4,
        "localTablesVersion": 1,
        "productionStatusOfProcessedData": 0,
        "discipline": 0,
        "parameterCategory": 16,
        "parameterNumber": 224,
        "productDefinitionTemplateNumber": 0,
        "typeOfFirstFixedSurface": 1,
        "typeOfSecondFixedSurface": 255,
        **changes,
    }


@pytest.mark.parametrize(
    "category,number,surface",
    [
        (16, 224, 1),
        (16, 225, 100),
        (7, 224, 1),
        (19, 224, 1),
        (3, 225, 1),
        (3, 226, 1),
        (3, 228, 1),
        (16, 226, 1),
    ],
)
def test_reviewed_codes_have_a_bounded_native_path(category, number, surface):
    grib.parameter_encoding(
        profile(
            parameterCategory=category,
            parameterNumber=number,
            typeOfFirstFixedSurface=surface,
        )
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"centre": 98},
        {"subCentre": 1},
        {"tablesVersion": 5},
        {"localTablesVersion": 2},
        {"productionStatusOfProcessedData": 4},
        {"productDefinitionTemplateNumber": 11},
        {"productDefinitionTemplateNumber": 8},
        {"parameterNumber": 227},
        {"typeOfFirstFixedSurface": 100},
        {"typeOfSecondFixedSurface": 8},
        {"productionStatusOfProcessedData": None},
        {"productionStatusOfProcessedData": False},
    ],
)
def test_local_table_support_does_not_admit_unknown_profiles(changes):
    with pytest.raises(SourceError) as exc:
        grib.parameter_encoding(profile(**changes))
    assert exc.value.context["reason"] == "unsupported_native_encoding"


@pytest.mark.parametrize("phase", [(0, 0, 0), (1, 2, 1)])
@pytest.mark.parametrize("surface", [1, 8])
def test_gfs_clear_sky_longwave_encoding_does_not_supply_an_implicit_unit(phase, surface):
    native = profile(
        localTablesVersion=1,
        parameterCategory=5,
        productDefinitionTemplateNumber=8,
        typeOfProcessedData=phase[0],
        typeOfGeneratingProcess=phase[1],
        significanceOfReferenceTime=phase[2],
        units="unknown",
        parameterUnits="224",
        typeOfFirstFixedSurface=surface,
    )
    grib.parameter_encoding(native)
    assert grib.source_value_unit(native) is None
    assert native["units"] == "unknown" and native["parameterUnits"] == "224"


@pytest.mark.parametrize(
    "changes",
    [
        {"centre": 98},
        {"subCentre": 1},
        {"tablesVersion": 5},
        {"localTablesVersion": 0},
        {"productionStatusOfProcessedData": 1},
        {"discipline": 2},
        {"parameterCategory": 4},
        {"parameterNumber": 225},
        {"productDefinitionTemplateNumber": 0},
        {"productDefinitionTemplateNumber": 11},
        {"typeOfFirstFixedSurface": 10},
        {"typeOfSecondFixedSurface": 8},
        {"typeOfGeneratingProcess": 0},
        {"typeOfProcessedData": False},
    ],
)
def test_gfs_local_energy_profile_does_not_admit_other_encodings(changes):
    native = profile(
        localTablesVersion=1,
        parameterCategory=5,
        productDefinitionTemplateNumber=8,
        typeOfProcessedData=1,
        typeOfGeneratingProcess=2,
        significanceOfReferenceTime=1,
    )
    native.update(changes)
    with pytest.raises(SourceError):
        grib.parameter_encoding(native)


def soil_layer(top, bottom):
    return {
        "bottom": {"type": "depth_below_land", "value": bottom, "unit": "m"},
        "top": {"type": "depth_below_land", "value": top, "unit": "m"},
    }


def write_file(path, records):
    with path.open("wb") as stream:
        for record in records:
            handle = eccodes.codes_grib_new_from_samples("regular_ll_sfc_grib2")
            try:
                settings = {
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
                    **profile(),
                    **{k: v for k, v in record.items() if k != "values"},
                }
                for key, value in settings.items():
                    eccodes.codes_set(handle, key, value)
                eccodes.codes_set_values(
                    handle, record.get("values", [1.0, 2.0, 3.0, 4.0])
                )
                eccodes.codes_write(handle, stream)
            finally:
                eccodes.codes_release(handle)


def configured(tmp_path, records, *, soil=False, source_unit=None, local=1):
    path = tmp_path / "controlled.grib2"
    write_file(path, records)
    name, unit = ("sw", "m3/m3") if soil else ("cdbz", "dbz")
    fixed = {"level_type": "depth_below_land", "level_unit": "m"} if soil else {}
    p = {
        "api_version": "cedarkit.parameters/v1",
        "id": "controlled.parameters",
        "version": "1",
        "parameters": [
            {
                "parameter_id": "example." + name,
                "name": name,
                "unit": unit,
                "fixed_conditions": fixed,
            }
        ],
    }
    native = (
        profile(
            parameterCategory=1,
            parameterNumber=0,
            typeOfFirstFixedSurface=106,
            typeOfSecondFixedSurface=106,
        )
        if soil
        else profile()
    )
    native["localTablesVersion"] = local
    m = {
        "api_version": "cedarkit.mappings/v1",
        "id": "controlled.maps",
        "version": "1",
        "backend": "grib2",
        "tables": [],
        "mappings": [
            {
                "id": name,
                "parameter_id": "example." + name,
                "backend": "grib2",
                "applies_to": {},
                "when": {},
                "native": {
                    "match": native,
                    "translate": {
                        "vertical": {"rule": "grib.fixed_surfaces"},
                        "time": {"rule": "grib.time"},
                        "unit": {
                            "rule": "common.value_unit",
                            "config": {"source_unit": source_unit or unit},
                        },
                    },
                },
                "evidence": [
                    "controlled regression using reviewed v12.6 encoding; no product scope"
                ],
            }
        ],
    }
    for filename, value in (("parameters.json", p), ("mappings.json", m)):
        (tmp_path / filename).write_text(json.dumps(value))
    return from_source(
        {"kind": "file", "path": str(path)},
        context={
            "parameter_registry": {"path": str(tmp_path / "parameters.json")},
            "mappings": {"grib2": {"path": str(tmp_path / "mappings.json")}},
        },
    )


def test_cdbz_public_query_and_value_unit_from_explicit_mapping(tmp_path):
    source = configured(tmp_path, [{"values": [10.0, 20.0, 30.0, 40.0]}])
    try:
        field = source.sel(parameter="cdbz").one()
        assert field.metadata["native_fields"]["productionStatusOfProcessedData"] == 0
        ds = field.to_xarray()
        np.testing.assert_array_equal(
            ds.cdbz.values.reshape(2, 2), [[10, 20], [30, 40]]
        )
        assert ds.cdbz.attrs["units"] == "dbz"
    finally:
        source.close()


@pytest.mark.parametrize("factor,top,bottom", [(2, 10, 40), (1, 1, 4)])
@pytest.mark.parametrize("local", [0, 1])
def test_soil_water_reinterpretation_and_equivalent_layer_encodings(
    tmp_path, factor, top, bottom, local
):
    source = configured(
        tmp_path,
        [
            {
                "parameterCategory": 1,
                "localTablesVersion": local,
                "parameterNumber": 0,
                "typeOfFirstFixedSurface": 106,
                "typeOfSecondFixedSurface": 106,
                "scaleFactorOfFirstFixedSurface": factor,
                "scaledValueOfFirstFixedSurface": top,
                "scaleFactorOfSecondFixedSurface": factor,
                "scaledValueOfSecondFixedSurface": bottom,
                "values": [0.125, 0.25, 0.375, 0.5],
            }
        ],
        soil=True,
        local=local,
    )
    try:
        field = source.sel(parameter="sw", layer=soil_layer(0.1, 0.4)).one()
        assert field.identity.to_dict()["layer"] == soil_layer(0.1, 0.4)
        assert field.metadata["source_unit"] == "m3/m3"
        assert field.metadata["source_unit_basis"]["elementcode"] == 144
        assert field.metadata["source_unit_basis"]["eccodes_derived_unit"] != "m3/m3"
        ds = field.to_xarray()
        np.testing.assert_array_equal(
            next(iter(ds.data_vars.values())).values.reshape(2, 2),
            [[0.125, 0.25], [0.375, 0.5]],
        )
    finally:
        source.close()


def test_soil_unit_override_is_limited_to_reviewed_producer_profile():
    native = profile(
        parameterCategory=1,
        parameterNumber=0,
        typeOfFirstFixedSurface=106,
        typeOfSecondFixedSurface=106,
        units="kg kg**-1",
    )
    assert grib.source_value_unit(native) == "m3/m3"
    assert grib.source_value_unit({**native, "localTablesVersion": 0}) == "m3/m3"
    assert grib.source_value_unit({**native, "centre": 98}) == "kg kg**-1"


@pytest.mark.parametrize(
    "changes",
    [
        {"centre": 98},
        {"subCentre": 1},
        {"tablesVersion": 5},
        {"localTablesVersion": 2},
        {"productionStatusOfProcessedData": 4},
        {"productDefinitionTemplateNumber": 1},
        {"typeOfFirstFixedSurface": 100},
        {"typeOfSecondFixedSurface": 255},
        {"parameterNumber": 1},
    ],
)
def test_local_zero_soil_override_rejects_other_contexts(changes):
    native = profile(
        localTablesVersion=0,
        parameterCategory=1,
        parameterNumber=0,
        typeOfFirstFixedSurface=106,
        typeOfSecondFixedSurface=106,
        units="kg kg**-1",
    )
    assert grib.source_value_unit({**native, **changes}) == "kg kg**-1"


@pytest.mark.parametrize("local", [0, 1])
def test_mapping_cannot_claim_specific_humidity_for_reviewed_soil_water(
    tmp_path, local
):
    source = configured(
        tmp_path,
        [
            {
                "parameterCategory": 1,
                "localTablesVersion": local,
                "parameterNumber": 0,
                "typeOfFirstFixedSurface": 106,
                "typeOfSecondFixedSurface": 106,
                "scaleFactorOfFirstFixedSurface": 2,
                "scaledValueOfFirstFixedSurface": 10,
                "scaleFactorOfSecondFixedSurface": 2,
                "scaledValueOfSecondFixedSurface": 40,
            }
        ],
        soil=True,
        source_unit="kg/kg",
        local=local,
    )
    try:
        with pytest.raises(SourceError) as exc:
            source.sel(parameter="sw").one()
        assert exc.value.context["reason"] == "inconsistent_native_metadata"
    finally:
        source.close()


def test_common_vertical_constraint_matches_layer_endpoints():
    identity = {"layer": soil_layer(0.1, 0.4)}
    assert matches(identity, {"level_type": "depth_below_land"})
    assert matches(identity, {"level_type": "depth_below_land", "level_unit": "cm"})
    assert not matches(identity, {"level_type": "pressure"})
    assert not matches(identity, {"level_type": "depth_below_land", "level": 0.4})


@pytest.mark.parametrize(
    "condition",
    [
        {"localTablesVersion": [0, 1]},
        {"localTablesVersion": {"range": {"start": 0, "end": 1}}},
    ],
)
def test_frozen_plan_filters_retain_native_selector_semantics(condition):
    # Plan freezes lists/dicts; acquisition must still perform membership.
    assert native_matches({"localTablesVersion": 1}, freeze(condition))
    assert not native_matches({"localTablesVersion": 2}, freeze(condition))


@pytest.mark.parametrize("phase", [(0, 0, 0), (1, 2, 1)])
@pytest.mark.parametrize(
    "dataset", ["cma_gfs_gmf", "cma_meso_1km", "cma_meso_3km", "cma_tym"]
)
def test_terrain_source_unit_is_limited_to_explicit_current_product(phase, dataset):
    from reki.translation.cemc_grib import terrain_source_unit

    native = profile(
        localTablesVersion=0,
        parameterCategory=3,
        parameterNumber=5,
        typeOfProcessedData=phase[0],
        typeOfGeneratingProcess=phase[1],
        significanceOfReferenceTime=phase[2],
        units="m",
        parameterUnits="gpm",
    )
    context = {
        "dataset": dataset,
        "product": "orig",
        "product_version": "current",
    }

    def resolve(meta=native, ctx=context, pid="cedarkit.zs", unit="Gpm"):
        return terrain_source_unit(
            meta, context=ctx, parameter_id=pid, source_unit=unit
        )

    assert resolve() == "Gpm"
    for key, value in [
        ("centre", 98),
        ("subCentre", 1),
        ("tablesVersion", 5),
        ("localTablesVersion", 1),
        ("productionStatusOfProcessedData", 1),
        ("productDefinitionTemplateNumber", 8),
        ("parameterNumber", 4),
        ("typeOfFirstFixedSurface", 100),
        ("typeOfSecondFixedSurface", 8),
        ("typeOfProcessedData", False),
        ("typeOfGeneratingProcess", 9),
        ("units", "unknown"),
        ("parameterUnits", "m"),
    ]:
        assert resolve({**native, key: value}) is None
    assert resolve(ctx={**context, "dataset": "cma_geps"}) is None
    assert resolve(ctx={}) is None
    assert resolve(ctx={**context, "product": "post"}) is None
    assert resolve(ctx={**context, "product_version": "next"}) is None
    assert resolve(pid="cedarkit.h") is None
    assert resolve(unit="m") is None
    assert resolve(unit=None) is None
    assert native["units"] == "m" and native["parameterUnits"] == "gpm"


@pytest.mark.parametrize("phase", [(0, 0, 0), (1, 2, 1)])
def test_explicit_sweat_source_unit_has_exact_producer_product_and_view_guards(phase):
    from reki.translation.cemc_grib import sweat_source_unit

    native = profile(
        localTablesVersion=0,
        parameterCategory=7,
        parameterNumber=5,
        typeOfProcessedData=phase[0],
        typeOfGeneratingProcess=phase[1],
        significanceOfReferenceTime=phase[2],
        units="Numeric",
        parameterUnits="Numeric",
    )
    ctx = {"dataset": "cma_gfs_gmf", "product": "orig", "product_version": "current"}

    def resolve(meta=native, context=ctx, pid="cedarkit.sweatidx", unit="1"):
        return sweat_source_unit(
            meta, context=context, parameter_id=pid, source_unit=unit
        )

    assert resolve() == "1"
    for k, v in [
        ("centre", 98),
        ("subCentre", 1),
        ("tablesVersion", 5),
        ("localTablesVersion", 1),
        ("productionStatusOfProcessedData", 1),
        ("parameterCategory", 1),
        ("parameterNumber", 19),
        ("productDefinitionTemplateNumber", 8),
        ("typeOfFirstFixedSurface", 100),
        ("typeOfSecondFixedSurface", 8),
        ("typeOfProcessedData", False),
        ("typeOfGeneratingProcess", 9),
        ("units", "K"),
        ("parameterUnits", "Code table 4.201"),
    ]:
        assert resolve({**native, k: v}) is None
    for dataset in ["cma_meso_1km", "cma_meso_3km", "cma_tym", "cma_geps"]:
        assert resolve(context={**ctx, "dataset": dataset}) is None
    assert resolve(context={}) is None
    assert resolve(context={**ctx, "product": "post"}) is None
    assert resolve(context={**ctx, "product_version": "next"}) is None
    assert resolve(pid="cedarkit.precitype") is None
    assert resolve(unit="%") is None
    assert resolve(unit=None) is None


@pytest.mark.parametrize("category", [7, 16])
def test_reviewed_local_member_forms_keep_precise_template_and_producer_guards(
    category,
):
    native = profile(
        productDefinitionTemplateNumber=1,
        parameterCategory=category,
        parameterNumber=224,
        typeOfFirstFixedSurface=1,
        typeOfSecondFixedSurface=255,
    )
    assert grib.applicability(native) == 1
    for key, value in [
        ("centre", 98),
        ("subCentre", 1),
        ("tablesVersion", 5),
        ("localTablesVersion", 2),
        ("productionStatusOfProcessedData", 4),
        ("productDefinitionTemplateNumber", 11),
        ("parameterNumber", 225),
        ("typeOfFirstFixedSurface", 100),
        ("typeOfSecondFixedSurface", 8),
    ]:
        with pytest.raises(SourceError) as exc:
            grib.applicability({**native, key: value})
        assert exc.value.context["reason"] == "unsupported_native_encoding"
    # Recognizing the member template supplies no CDBZ/DCAPE unit or identity.
    assert grib.source_value_unit({**native, "units": "unknown"}) is None


@pytest.mark.parametrize("phase", [(3, 4, 0), (3, 4, 1), (4, 4, 0), (4, 4, 1)])
def test_geps_terrain_unit_uses_own_member_product_declaration(phase):
    from reki.translation.cemc_grib import terrain_source_unit

    native = profile(
        localTablesVersion=0,
        productDefinitionTemplateNumber=1,
        parameterCategory=3,
        parameterNumber=5,
        typeOfProcessedData=phase[0],
        typeOfGeneratingProcess=phase[1],
        significanceOfReferenceTime=phase[2],
        units="m",
        parameterUnits="gpm",
    )
    context = {"dataset": "cma_geps", "product": "orig", "product_version": "current"}

    def resolve(meta=native, ctx=context, pid="cedarkit.zs", unit="Gpm"):
        return terrain_source_unit(
            meta, context=ctx, parameter_id=pid, source_unit=unit
        )

    assert resolve() == "Gpm"
    for key, value in [
        ("centre", 98),
        ("localTablesVersion", 1),
        ("productDefinitionTemplateNumber", 0),
        ("parameterNumber", 4),
        ("typeOfProcessedData", False),
        ("typeOfGeneratingProcess", 2),
        ("units", "unknown"),
        ("parameterUnits", "m"),
    ]:
        assert resolve({**native, key: value}) is None
    for dataset in ["cma_reps", "cma_gfs_gmf", "cma_meso_1km", "cma_tym"]:
        assert resolve(ctx={**context, "dataset": dataset}) is None
    assert resolve(ctx={**context, "product_version": "next"}) is None
    assert resolve(pid="cedarkit.h") is None
    assert resolve(unit="m") is None
