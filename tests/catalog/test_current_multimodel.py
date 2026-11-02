"""Independent native fixtures for reviewed current deterministic product extensions."""

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


def encoded(
    path, name, hour=6, *, system="meso3", values=(0, 9999, -1.25, 2.5), **changes
):
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
            if name in {"cdbz", "dbz", "fogh", "ht0", "znt", "dcape"}
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
            indicatorOfUnitOfTimeRange=0 if system == "meso1" else 1,
            forecastTime=hour * 60 if system == "meso1" else hour,
            bitmapPresent=1,
            missingValue=9999,
        )
        if first == 100:
            settings.update(
                scaleFactorOfFirstFixedSurface=1, scaledValueOfFirstFixedSurface=700000
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


EXPECTED = {
    "meso1": [
        "h",
        "w",
        "div",
        "td",
        "ttd",
        "rh2m",
        "td2m",
        "cape",
        "cin",
        "dcape",
        "pli",
        "bli",
        "tcc",
        "lcc",
        "mcc",
        "hcc",
        "cc",
        "vis",
        "qc",
        "qr",
        "qs",
        "qi",
        "graupel",
        "q2m",
        "ts",
        "zs",
        "theta-se",
        "tvw",
        "tiw",
        "cdbz",
        "dbz",
        "pblh",
        "ht0",
        "shr-0-1000",
        "shr-0-3000",
        "shr-0-6000",
    ],
    "meso3": [
        "h",
        "w",
        "div",
        "vor",
        "td",
        "ttd",
        "rh2m",
        "td2m",
        "cape",
        "cin",
        "dcape",
        "pli",
        "bli",
        "tcc",
        "lcc",
        "mcc",
        "hcc",
        "cc",
        "pwat",
        "vis",
        "qc",
        "qr",
        "qs",
        "qi",
        "graupel",
        "q2m",
        "ts",
        "zs",
        "theta-se",
        "si",
        "tvw",
        "tcw",
        "tiw",
        "cdbz",
        "dbz",
        "ceiling",
        "pblh",
        "ht0",
        "shr-0-1000",
        "shr-0-3000",
        "shr-0-6000",
    ],
    "tym": [
        "h",
        "w",
        "div",
        "vor",
        "td",
        "ttd",
        "rh2m",
        "td2m",
        "cape",
        "cin",
        "bli",
        "tcc",
        "lcc",
        "cc",
        "pwat",
        "vis",
        "qc",
        "qr",
        "qs",
        "qi",
        "graupel",
        "q2m",
        "ts",
        "zs",
        "theta-se",
        "cdbz",
        "fogh",
        "shr-0-1000",
        "shr-0-3000",
        "shr-0-6000",
    ],
}
ALIASES = {"meso1": "CMA-MESO-1KM", "meso3": "CMA-MESO-3KM", "tym": "CMA-TYM"}


@pytest.mark.parametrize("system", EXPECTED)
@pytest.mark.parametrize("hour", [0, 18])
def test_reviewed_product_fields_preserve_values_carriers_and_actual_time_units(
    tmp_path, system, hour
):
    path = tmp_path / "fields.grib2"
    messages = []
    for name in EXPECTED[system]:
        encoded(path, name, hour, system=system)
        messages.append(path.read_bytes())
    path.write_bytes(b"".join(messages))
    with from_source(
        {"kind": "file", "dataset": ALIASES[system], "path": str(path)}
    ) as source:
        fields = source.sel(
            [
                {"parameter": "cedarkit." + name, **carrier(name), "step": f"PT{hour}H"}
                for name in EXPECTED[system]
            ]
        ).all()
        assert len(fields) == len(EXPECTED[system])
        ds = fields.to_xarray()
        assert len(ds.data_vars) == len(EXPECTED[system])
        np.testing.assert_array_equal(ds.latitude.values, [50, 49])
        np.testing.assert_array_equal(ds.longitude.values, [100, 101])
        for field in fields:
            identity = field.identity.to_dict()
            name = identity["parameter"].removeprefix("cedarkit.")
            var = variable(ds, name)
            np.testing.assert_allclose(
                var.values.reshape(-1),
                [0, np.nan, -1.25, 2.5],
                rtol=0,
                atol=0,
                equal_nan=True,
            )
            assert var.attrs["units"] == CASES[name][4]
            assert identity["valid_time"] == (
                "2026-10-31T12:00:00Z" if hour == 0 else "2026-11-01T06:00:00Z"
            )
            assert "member" not in identity
            if CASES[name][2] == 100:
                assert identity["level"] == 700
            if CASES[name][3] in {8, 103}:
                assert identity["layer"] == carrier(name)["layer"]
            meta = thaw(field.metadata)
            assert meta["statistics"] == {
                "over": "time",
                "operation": "instantaneous",
            } and not meta.get("statistical_interval")
            assert meta["native_fields"]["indicatorOfUnitOfTimeRange"] == (
                0 if system == "meso1" else 1
            )
            if name == "zs":
                assert (
                    meta["source_unit"] == "Gpm"
                    and meta["native_fields"]["units"] == "m"
                )
        with pytest.raises(CompletenessError):
            source.sel(parameter="cedarkit.h", level_type="pressure").all(
                completeness="required"
            )


@pytest.mark.parametrize(
    "system,name",
    [
        ("meso1", "vor"),
        ("meso1", "pwat"),
        ("meso3", "fogh"),
        ("tym", "dcape"),
        ("tym", "dbz"),
    ],
)
def test_unverified_product_pairs_are_not_registered(tmp_path, system, name):
    path = tmp_path / "unused.grib2"
    path.touch()
    with from_source(
        {"kind": "file", "dataset": ALIASES[system], "path": str(path)}
    ) as source:
        with pytest.raises(QueryError):
            source.sel(parameter="cedarkit." + name, **carrier(name)).explain()


@pytest.mark.parametrize(
    "name,changes",
    [
        ("h", {"typeOfFirstFixedSurface": 1}),
        ("cdbz", {"productDefinitionTemplateNumber": 8}),
        ("w", {"productDefinitionTemplateNumber": 8}),
        ("q2m", {"scaledValueOfFirstFixedSurface": 3}),
        ("shr-0-1000", {"scaledValueOfFirstFixedSurface": 2}),
        ("cdbz", {"localTablesVersion": 0}),
        ("zs", {"tablesVersion": 5}),
    ],
)
def test_product_bindings_keep_instantaneous_identity_and_real_fixed_conditions(
    tmp_path, name, changes
):
    path = tmp_path / "bad.grib2"
    encoded(path, name, **changes)
    with from_source(
        {"kind": "file", "dataset": "CMA-MESO-3KM", "path": str(path)}
    ) as source:
        with pytest.raises(QueryError) as error:
            source.sel(parameter="cedarkit." + name, **carrier(name)).one()
        assert error.value.code == "no_match"


@pytest.mark.parametrize("system", EXPECTED)
def test_terrain_reinterpretation_does_not_hide_other_unit_conflicts(
    tmp_path, monkeypatch, system
):
    from reki.translation import grib_backend

    path = tmp_path / "unit.grib2"
    encoded(path, "zs", system=system)
    original = grib_backend._metadata

    def metadata(handle, **kwargs):
        r = original(handle, **kwargs)
        r["units"] = "kg/kg"
        return r

    monkeypatch.setattr(grib_backend, "_metadata", metadata)
    with from_source(
        {"kind": "file", "dataset": ALIASES[system], "path": str(path)}
    ) as source:
        with pytest.raises(SourceError):
            source.sel(parameter="cedarkit.zs", level_type="surface").one()


@pytest.mark.parametrize("hour", [0, 18])
def test_explicitly_unitless_sweat_score_preserves_values_without_probability_scaling(
    tmp_path, hour
):
    CASES["sweatidx"] = (7, 5, 1, 255, "1")
    path = tmp_path / "score.grib2"
    encoded(path, "sweatidx", hour, values=(0, 9999, -1.25, 350.5))
    with from_source(
        {"kind": "file", "dataset": "CMA-GFS", "path": str(path)}
    ) as source:
        field = source.sel(parameter="cedarkit.sweatidx", level_type="surface").one()
        ds = field.to_xarray()
        np.testing.assert_allclose(
            variable(ds, "sweatidx").values.reshape(-1),
            [0, np.nan, -1.25, 350.5],
            rtol=0,
            atol=0,
            equal_nan=True,
        )
        assert ds.sweatidx.attrs["units"] == "1"
        meta = thaw(field.metadata)
        assert meta["source_unit"] == "1"
        assert (
            meta["native_fields"]["units"]
            == meta["native_fields"]["parameterUnits"]
            == "Numeric"
        )
        assert "explicitly no unit" in meta["source_unit_basis"]["origin"]
        assert (
            "member" not in field.identity.to_dict()
            and meta["statistics"]["operation"] == "instantaneous"
        )


def test_sweat_unit_role_does_not_hide_a_real_unit_conflict(tmp_path, monkeypatch):
    from reki.translation import grib_backend

    CASES["sweatidx"] = (7, 5, 1, 255, "1")
    path = tmp_path / "unit.grib2"
    encoded(path, "sweatidx")
    original = grib_backend._metadata

    def metadata(handle, **kwargs):
        r = original(handle, **kwargs)
        r["units"] = "K"
        return r

    monkeypatch.setattr(grib_backend, "_metadata", metadata)
    with from_source(
        {"kind": "file", "dataset": "CMA-GFS", "path": str(path)}
    ) as source:
        with pytest.raises(SourceError):
            source.sel(parameter="cedarkit.sweatidx", level_type="surface").one()


def test_canonical_residuals_skip_unselected_grids_without_changing_query_results(
    tmp_path, monkeypatch
):
    from reki.translation import grib_backend

    path = tmp_path / "layers.grib2"
    messages = []
    for level in [50000, 70000]:
        encoded(
            path,
            "h",
            scaleFactorOfFirstFixedSurface=0,
            scaledValueOfFirstFixedSurface=level,
        )
        messages.append(path.read_bytes())
    path.write_bytes(b"".join(messages))
    decoded = []
    original = grib_backend._grid

    def grid(handle):
        decoded.append(eccodes.codes_get_long(handle, "scaledValueOfFirstFixedSurface"))
        return original(handle)

    monkeypatch.setattr(grib_backend, "_grid", grid)
    with from_source(
        {"kind": "file", "dataset": "CMA-MESO-3KM", "path": str(path)}
    ) as source:
        field = source.sel(
            parameter="cedarkit.h", level_type="pressure", level=700
        ).one()
        assert field.identity.to_dict()["level"] == 700 and decoded == [70000]
        assert (
            len(
                source.sel(
                    parameter="cedarkit.h", level_type="pressure", level=600
                ).all()
            )
            == 0
        )
        assert decoded == [70000]
