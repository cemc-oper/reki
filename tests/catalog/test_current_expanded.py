"""Twenty-five reviewed current GFS instantaneous identities share finite native rules."""

import eccodes
import numpy as np
import pytest

from cedarkit_query import CompletenessError, QueryError, SourceError
from reki import from_source
from reki.catalog.model import thaw

# Independent native cases from original object probes and actual producer headers.
CASES = {
    "qc": (1, 22, 100, 255, "kg/kg"),
    "qr": (1, 24, 100, 255, "kg/kg"),
    "qs": (1, 25, 100, 255, "kg/kg"),
    "qi": (1, 23, 100, 255, "kg/kg"),
    "graupel": (1, 32, 100, 255, "kg/kg"),
    "q2m": (1, 0, 103, 255, "kg/kg"),
    "ts": (0, 0, 1, 255, "K"),
    "zs": (3, 5, 1, 255, "Gpm"),
    "theta-se": (0, 3, 100, 255, "K"),
    "si": (7, 13, 1, 255, "K"),
    "tvw": (1, 64, 10, 255, "kg/m2"),
    "tcw": (1, 69, 10, 255, "kg/m2"),
    "tiw": (1, 70, 10, 255, "kg/m2"),
    "cdbz": (16, 224, 1, 255, "dbz"),
    "dbz": (16, 225, 100, 255, "dbz"),
    "ceiling": (6, 13, 1, 255, "m"),
    "fogh": (19, 224, 1, 255, "m"),
    "pblh": (3, 18, 1, 255, "m"),
    "ht0": (3, 225, 1, 255, "m"),
    "znt": (3, 228, 1, 255, "m"),
    "albedo": (19, 1, 1, 255, "%"),
    "sd": (1, 11, 1, 255, "m"),
    "shr-0-1000": (2, 25, 103, 103, "s-1"),
    "shr-0-3000": (2, 25, 103, 103, "s-1"),
    "shr-0-6000": (2, 25, 103, 103, "s-1"),
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
            localTablesVersion=1
            if name in {"cdbz", "dbz", "fogh", "ht0", "znt"}
            else 0,
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
        if second == 103:
            settings.update(
                scaleFactorOfFirstFixedSurface=-3,
                scaledValueOfFirstFixedSurface=int(name.split("-")[-1]) // 1000,
                scaleFactorOfSecondFixedSurface=-3,
                scaledValueOfSecondFixedSurface=0,
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
    if second == 103:
        return {
            "layer": {
                "bottom": {"type": "height_above_ground", "value": 0, "unit": "m"},
                "top": {
                    "type": "height_above_ground",
                    "value": int(name.split("-")[-1]),
                    "unit": "m",
                },
            }
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
def test_expanded_instantaneous_fields_preserve_values_masks_units_and_carriers(
    tmp_path, name
):
    path = tmp_path / "instant.grib2"
    encoded(path, name)
    with from_source(
        {"kind": "file", "dataset": "CMA-GFS", "path": str(path)}
    ) as source:
        field = source.sel(
            parameter="cedarkit." + name,
            **carrier(name),
            time="2026-10-31T12:00:00Z",
            step="PT6H",
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
        elif second == 103:
            assert identity["layer"] == carrier(name)["layer"]
            assert value.attrs["layer_top_value"] == int(name.split("-")[-1])
            assert value.attrs["layer_bottom_value"] == 0
        elif first == 103:
            assert identity["level"] == 2
        else:
            assert identity["level_type"] == (
                "entire_atmosphere" if name in {"tvw", "tcw", "tiw"} else "surface"
            )
        if name == "zs":
            assert field.metadata["native_fields"]["units"] == "m"
            assert field.metadata["native_fields"]["parameterUnits"] == "gpm"
            assert field.metadata["source_unit"] == "Gpm"
            assert "producer" in field.metadata["source_unit_basis"]["origin"]
        metadata = thaw(field.metadata)
        assert metadata["statistics"] == {"operation": "instantaneous", "over": "time"}
        assert not metadata.get("statistical_interval")
        with pytest.raises(CompletenessError):
            source.sel(parameter="cedarkit." + name, **carrier(name)).all(
                completeness="required"
            )


@pytest.mark.parametrize("name", ["qc", "q2m", "zs", "tvw", "cdbz", "shr-0-1000"])
def test_initial_instantaneous_groups_are_not_zero_length_accumulations(tmp_path, name):
    path = tmp_path / "initial.grib2"
    encoded(path, name, 0)
    with from_source(
        {"kind": "file", "dataset": "CMA-GFS", "path": str(path)}
    ) as source:
        field = source.sel(parameter="cedarkit." + name, **carrier(name)).one()
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
        ("qc", {"typeOfFirstFixedSurface": 1}),
        ("q2m", {"scaledValueOfFirstFixedSurface": 3}),
        ("tvw", {"typeOfFirstFixedSurface": 1}),
        ("cdbz", {"localTablesVersion": 0}),
        ("cdbz", {"centre": 98}),
        ("dbz", {"parameterNumber": 226}),
        ("zs", {"tablesVersion": 5}),
        ("ts", {"productDefinitionTemplateNumber": 8}),
        ("sd", {"typeOfGeneratingProcess": 0}),
        ("shr-0-1000", {"scaledValueOfFirstFixedSurface": 2}),
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
            source.sel(parameter="cedarkit." + name, **carrier(name)).one()
        assert error.value.code == "no_match"


@pytest.mark.parametrize(
    "name,unit",
    [
        ("zs", "kg/kg"),
        ("zs", "m**2/s**2"),
        ("qc", "kg/m2"),
        ("tvw", "kg/kg"),
        ("q2m", "%"),
        ("si", "degC"),
        ("shr-0-1000", "m/s"),
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
            source.sel(parameter="cedarkit." + name, **carrier(name)).one()
        assert error.value.context["reason"] == "inconsistent_native_metadata"


def test_expanded_fields_assemble_and_preserve_distinct_named_layer_variables(tmp_path):
    path = tmp_path / "expanded.grib2"
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
                    "parameter": "cedarkit." + name,
                    **carrier(name),
                    "time": "2026-10-31T12:00:00Z",
                    "step": "PT6H",
                }
                for name in CASES
            ]
        ).all()
        assert len(fields) == 25
        dataset = fields.to_xarray()
        assert len(dataset.data_vars) == 25
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
        "qc",
        18,
        scaleFactorOfFirstFixedSurface=0,
        scaledValueOfFirstFixedSurface=65000,
    )
    with from_source(
        {"kind": "file", "dataset": "CMA-GFS", "path": str(path)}
    ) as source:
        field = source.sel(
            parameter="qc", level_type="pressure", level=650, step="PT18H"
        ).one()
        assert field.identity.to_dict()["level"] == 650
        assert (
            len(source.sel(parameter="qc", level_type="pressure", level=600).all()) == 0
        )
        assert len(source.sel(parameter="qc", level_type="pressure", step="PT6H").all()) == 0


@pytest.mark.parametrize(
    "system", ["CMA-GEPS", "CMA-REPS"]
)
def test_gfs_pressure_height_binding_does_not_register_other_systems(tmp_path, system):
    path = tmp_path / "unopened"
    path.touch()
    with from_source({"kind": "file", "dataset": system, "path": str(path)}) as source:
        with pytest.raises(QueryError):
            source.sel(parameter="qc").explain()
