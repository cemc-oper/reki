"""Twenty reviewed current GFS instantaneous identities share finite native rules."""

import eccodes
import numpy as np
import pytest

from cedarkit_query import CompletenessError, QueryError, SourceError
from reki import from_source
from reki.catalog.model import thaw

# Independent native cases from original object probes and actual producer headers.
CASES = {
    "h": (3, 5, 100, 255, "Gpm"),
    "w": (2, 9, 100, 255, "m/s"),
    "div": (2, 13, 100, 255, "s-1"),
    "vor": (2, 12, 100, 255, "s-1"),
    "td": (0, 6, 100, 255, "K"),
    "ttd": (0, 7, 100, 255, "K"),
    "rh2m": (1, 1, 103, 255, "%"),
    "td2m": (0, 6, 103, 255, "K"),
    "cape": (7, 6, 1, 255, "J/kg"),
    "cin": (7, 7, 1, 255, "J/kg"),
    "dcape": (7, 224, 1, 255, "J/kg"),
    "pli": (7, 0, 1, 255, "K"),
    "bli": (7, 1, 1, 255, "K"),
    "tcc": (6, 1, 1, 8, "%"),
    "lcc": (6, 3, 1, 8, "%"),
    "mcc": (6, 4, 1, 8, "%"),
    "hcc": (6, 5, 1, 8, "%"),
    "cc": (6, 22, 100, 255, "%"),
    "pwat": (1, 3, 10, 255, "kg/m2"),
    "vis": (19, 0, 1, 255, "m"),
}


def encoded(path, name, hour=6, *, values=(0, 9999, -1.25, 2.5), **changes):
    category, number, first, second, _ = CASES[name]
    g = eccodes.codes_grib_new_from_samples("regular_ll_sfc_grib2")
    try:
        settings = dict(
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
            localTablesVersion=1 if name == "dcape" else 0,
            productionStatusOfProcessedData=0,
            typeOfProcessedData=0 if hour == 0 else 1,
            typeOfGeneratingProcess=0 if hour == 0 else 2,
            significanceOfReferenceTime=0 if hour == 0 else 1,
            productDefinitionTemplateNumber=0,
            discipline=0,
            parameterCategory=category,
            parameterNumber=number,
            typeOfFirstFixedSurface=first,
            typeOfSecondFixedSurface=second,
            dataDate=20261031,
            dataTime=1200,
            indicatorOfUnitOfTimeRange=1,
            forecastTime=hour,
            bitmapPresent=1,
            missingValue=9999,
        )
        if first == 100:
            settings.update(
                scaleFactorOfFirstFixedSurface=1, scaledValueOfFirstFixedSurface=600000
            )
        if first == 103:
            settings.update(
                scaleFactorOfFirstFixedSurface=0, scaledValueOfFirstFixedSurface=2
            )
        settings.update(changes)
        for key, value in settings.items():
            eccodes.codes_set(g, key, value)
        eccodes.codes_set_values(g, values)
        path.write_bytes(eccodes.codes_get_message(g))
    finally:
        eccodes.codes_release(g)


def carrier(name):
    first, second = CASES[name][2:4]
    if second == 8:
        return {
            "layer": {"bottom": {"type": "surface"}, "top": {"type": "atmosphere_top"}}
        }
    return {
        "level_type": {
            100: "pressure",
            103: "height_above_ground",
            10: "entire_atmosphere",
            1: "surface",
        }[first]
    }


def variable(dataset, name):
    return next(
        v
        for v in dataset.data_vars.values()
        if v.attrs["cedarkit_parameter_id"] == "cedarkit." + name
    )


@pytest.mark.parametrize("name", CASES)
def test_twenty_instantaneous_fields_preserve_values_masks_units_and_carriers(
    tmp_path, name
):
    path = tmp_path / "instant.grib2"
    encoded(path, name)
    with from_source(
        {"kind": "file", "dataset": "CMA-GFS", "path": str(path)}
    ) as source:
        field = source.sel(
            parameter=name, **carrier(name), time="2026-10-31T12:00:00Z", step="PT6H"
        ).one()
        dataset = field.to_xarray()
        value = variable(dataset, name)
        np.testing.assert_allclose(
            value.values.reshape(-1),
            [0, np.nan, -1.25, 2.5],
            rtol=0,
            atol=0,
            equal_nan=True,
        )
        assert value.attrs["units"] == CASES[name][4]
        identity = field.identity.to_dict()
        assert identity["valid_time"] == "2026-10-31T18:00:00Z"
        assert "member" not in identity
        first, second = CASES[name][2:4]
        if first == 100:
            assert identity["level_type"] == "pressure" and identity["level"] == 600
            assert dataset.pressure.attrs["units"] == "hPa"
        elif first == 103:
            assert (
                identity["level_type"] == "height_above_ground"
                and identity["level"] == 2
            )
        elif second == 8:
            assert identity["layer"] == {
                "bottom": {"type": "surface"},
                "top": {"type": "atmosphere_top"},
            }
            assert value.attrs["layer_bottom_type"] == "surface"
            assert value.attrs["layer_top_type"] == "atmosphere_top"
            assert (
                "layer_bottom_value" not in value.attrs
                and "layer_top_value" not in value.attrs
            )
        else:
            assert identity["level_type"] == (
                "entire_atmosphere" if name == "pwat" else "surface"
            )
        metadata = thaw(field.metadata)
        assert metadata["statistics"] == {"operation": "instantaneous", "over": "time"}
        assert not metadata.get("statistical_interval")
        with pytest.raises(CompletenessError):
            source.sel(parameter=name, **carrier(name)).all(completeness="required")


@pytest.mark.parametrize("name", ["h", "td2m", "cape", "dcape", "tcc", "pwat"])
def test_initial_instantaneous_groups_are_not_zero_length_accumulations(tmp_path, name):
    path = tmp_path / "initial.grib2"
    encoded(path, name, 0)
    with from_source(
        {"kind": "file", "dataset": "CMA-GFS", "path": str(path)}
    ) as source:
        field = source.sel(parameter=name, **carrier(name)).one()
        assert field.identity.to_dict()["step"] == "PT0S"
        assert thaw(field.metadata)["statistics"]["operation"] == "instantaneous"
        np.testing.assert_allclose(
            variable(field.to_xarray(), name).values.reshape(-1),
            [0, np.nan, -1.25, 2.5],
            rtol=0,
            atol=0,
            equal_nan=True,
        )


@pytest.mark.parametrize(
    "name,changes",
    [
        ("h", {"typeOfFirstFixedSurface": 1}),
        ("h", {"parameterNumber": 4}),
        ("w", {"parameterNumber": 8}),
        ("td", {"parameterNumber": 7}),
        ("rh2m", {"scaledValueOfFirstFixedSurface": 3}),
        ("td2m", {"scaledValueOfFirstFixedSurface": 3}),
        ("tcc", {"typeOfSecondFixedSurface": 255}),
        ("pwat", {"typeOfFirstFixedSurface": 1}),
        ("dcape", {"localTablesVersion": 0}),
        ("dcape", {"centre": 98}),
        ("vis", {"productDefinitionTemplateNumber": 8}),
        ("cape", {"typeOfGeneratingProcess": 0}),
    ],
)
def test_instantaneous_bindings_reject_wrong_identity_layer_and_context(
    tmp_path, name, changes
):
    path = tmp_path / "wrong.grib2"
    encoded(path, name, **changes)
    with from_source(
        {"kind": "file", "dataset": "CMA-GFS", "path": str(path)}
    ) as source:
        with pytest.raises(QueryError) as error:
            source.sel(parameter=name, **carrier(name)).one()
        assert error.value.code == "no_match"


@pytest.mark.parametrize(
    "name,unit",
    [
        ("h", "m"),
        ("w", "Pa/s"),
        ("pwat", "kg/kg"),
        ("pwat", "mm"),
        ("rh2m", "1"),
        ("ttd", "degC"),
    ],
)
def test_instantaneous_source_unit_conflicts_are_not_silently_converted(
    tmp_path, monkeypatch, name, unit
):
    from reki.translation import grib_backend

    path = tmp_path / "units.grib2"
    encoded(path, name)
    original = grib_backend._metadata

    def metadata(handle, **kwargs):
        result = original(handle, **kwargs)
        result["units"] = unit
        return result

    monkeypatch.setattr(grib_backend, "_metadata", metadata)
    with from_source(
        {"kind": "file", "dataset": "CMA-GFS", "path": str(path)}
    ) as source:
        with pytest.raises(SourceError) as error:
            source.sel(parameter=name, **carrier(name)).one()
        assert error.value.context["reason"] == "inconsistent_native_metadata"


def test_twenty_fields_assemble_and_preserve_distinct_named_layer_variables(tmp_path):
    path = tmp_path / "twenty.grib2"
    messages = []
    for name in CASES:
        encoded(path, name)
        messages.append(path.read_bytes())
    path.write_bytes(b"".join(messages))
    with from_source(
        {"kind": "file", "dataset": "CMA-GFS", "path": str(path)}
    ) as source:
        fields = source.sel(
            [
                {
                    "parameter": name,
                    **carrier(name),
                    "time": "2026-10-31T12:00:00Z",
                    "step": "PT6H",
                }
                for name in CASES
            ]
        ).all()
        assert len(fields) == 20
        dataset = fields.to_xarray()
        assert len(dataset.data_vars) == 20
        assert dataset.sizes["pressure"] == dataset.sizes["height_above_ground"] == 1
        for name in CASES:
            np.testing.assert_allclose(
                variable(dataset, name).values.reshape(-1),
                [0, np.nan, -1.25, 2.5],
                rtol=0,
                atol=0,
                equal_nan=True,
            )


def test_generic_pressure_and_unsampled_lead_remain_readable_with_explicit_caller_filters(
    tmp_path,
):
    path = tmp_path / "unlisted.grib2"
    encoded(
        path,
        "h",
        18,
        scaleFactorOfFirstFixedSurface=0,
        scaledValueOfFirstFixedSurface=65000,
    )
    with from_source(
        {"kind": "file", "dataset": "CMA-GFS", "path": str(path)}
    ) as source:
        field = source.sel(
            parameter="h", level_type="pressure", level=650, step="PT18H"
        ).one()
        assert field.identity.to_dict()["level"] == 650
        assert (
            len(source.sel(parameter="h", level_type="pressure", level=600).all()) == 0
        )
        assert len(source.sel(parameter="h", step="PT6H").all()) == 0


@pytest.mark.parametrize(
    "system", ["CMA-GEPS", "CMA-REPS"]
)
def test_unreviewed_wind_index_is_not_registered_in_member_products(tmp_path, system):
    path = tmp_path / "unopened"
    path.touch()
    with from_source({"kind": "file", "dataset": system, "path": str(path)}) as source:
        with pytest.raises(QueryError):
            source.sel(parameter="wi").explain()
