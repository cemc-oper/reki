"""Independent encoded cases for current GEPS/REPS instantaneous extensions."""

import eccodes
import numpy as np
import pytest
from cedarkit_query import CompletenessError, QueryError, SourceError

from reki import from_source
from reki.catalog.model import thaw

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

OPENED = {
    "GEPS": [
        "h",
        "rh2m",
        "cape",
        "cin",
        "dcape",
        "bli",
        "tcc",
        "lcc",
        "mcc",
        "hcc",
        "pwat",
        "vis",
        "zs",
        "cdbz",
        "shr-0-1000",
        "shr-0-3000",
        "shr-0-6000",
    ],
    "REPS": [
        "h",
        "rh2m",
        "cape",
        "cin",
        "dcape",
        "bli",
        "vis",
        "qc",
        "ts",
        "sd",
        "cdbz",
        "shr-0-1000",
        "shr-0-3000",
        "shr-0-6000",
    ],
}


def encoded(path, name, member=0, hour=6, *, system="GEPS", **changes):
    category, number, first, second, _ = CASES[name]
    g = eccodes.codes_grib_new_from_samples("regular_ll_sfc_grib2")
    try:
        native = {
            "Ni": 2,
            "Nj": 2,
            "latitudeOfFirstGridPointInDegrees": 50,
            "latitudeOfLastGridPointInDegrees": 49,
            "longitudeOfFirstGridPointInDegrees": 100,
            "longitudeOfLastGridPointInDegrees": 101,
            "iDirectionIncrementInDegrees": 1,
            "jDirectionIncrementInDegrees": 1,
            "centre": 38,
            "subCentre": 0,
            "tablesVersion": 4,
            "localTablesVersion": 1 if name in {"cdbz", "dcape"} else 0,
            "productionStatusOfProcessedData": 0,
            "productDefinitionTemplateNumber": 1,
            "typeOfProcessedData": 3 if member == 0 else 4,
            "typeOfGeneratingProcess": 4,
            "significanceOfReferenceTime": 0 if hour == 0 else 1,
            "typeOfEnsembleForecast": 0 if member == 0 else 3 if member % 2 else 2,
            "perturbationNumber": member,
            "numberOfForecastsInEnsemble": 31 if system == "GEPS" else 0,
            "discipline": 0,
            "parameterCategory": category,
            "parameterNumber": number,
            "typeOfFirstFixedSurface": first,
            "typeOfSecondFixedSurface": second,
            "dataDate": 20261101,
            "dataTime": 1200 if system == "GEPS" else 600,
            "indicatorOfUnitOfTimeRange": 1,
            "forecastTime": hour,
            "bitmapPresent": 1,
            "missingValue": 9999,
        }
        if first == 100:
            native.update(
                scaleFactorOfFirstFixedSurface=1, scaledValueOfFirstFixedSurface=650000
            )
        if first == 103:
            native.update(
                scaleFactorOfFirstFixedSurface=0, scaledValueOfFirstFixedSurface=2
            )
        if name.startswith("shr-"):
            native.update(
                scaledValueOfFirstFixedSurface=int(name.rsplit("-", 1)[1]),
                scaleFactorOfSecondFixedSurface=0,
                scaledValueOfSecondFixedSurface=0,
            )
        native.update(changes)
        for k, v in native.items():
            eccodes.codes_set(g, k, v)
        eccodes.codes_set_values(g, [0, 9999, -1.25, 2.5])
        with path.open("wb") as f:
            eccodes.codes_write(g, f)
    finally:
        eccodes.codes_release(g)


def carrier(name):
    first, second = CASES[name][2:4]
    if name.startswith("shr-"):
        return {
            "layer": {
                "top": {
                    "type": "height_above_ground",
                    "value": int(name.rsplit("-", 1)[1]),
                    "unit": "m",
                },
                "bottom": {"type": "height_above_ground", "value": 0, "unit": "m"},
            }
        }
    if second == 8:
        return {
            "layer": {"bottom": {"type": "surface"}, "top": {"type": "atmosphere_top"}}
        }
    if first == 100:
        return {"level_type": "pressure"}
    if first == 103:
        return {"level_type": "height_above_ground", "level": 2, "level_unit": "m"}
    return {"level_type": "entire_atmosphere" if first == 10 else "surface"}


@pytest.mark.parametrize("system", ["GEPS", "REPS"])
@pytest.mark.parametrize("member,hour", [(0, 0), (5, 18)])
def test_public_member_extensions_preserve_values_and_unlisted_coordinates(
    tmp_path, system, member, hour
):
    path = tmp_path / "fields.grib2"
    blobs = []
    for name in OPENED[system]:
        encoded(path, name, member, hour, system=system)
        blobs.append(path.read_bytes())
    path.write_bytes(b"".join(blobs))
    with from_source(
        {"kind": "file", "dataset": "CMA-" + system, "path": str(path)}
    ) as source:
        queries = [
            {
                "parameter": "cedarkit." + name,
                "member": member,
                "step": f"PT{hour}H",
                **carrier(name),
            }
            for name in OPENED[system]
        ]
        fields = source.sel(queries).all()
        assert len(fields) == len(OPENED[system])
        dataset = fields.to_xarray()
        assert len(dataset.data_vars) == len(OPENED[system])
        assert dataset.pressure.values.tolist() == [650]
        assert dataset.member.values.tolist() == [member]
        assert dataset.member_role.values.tolist() == [
            "control" if member == 0 else "perturbation"
        ]
        for field in fields:
            identity = field.identity.to_dict()
            name = identity["parameter"].removeprefix("cedarkit.")
            assert (
                identity["member"] == member and identity["step"] == f"PT{hour * 3600}S"
            )
            assert identity["member_role"] == (
                "control" if member == 0 else "perturbation"
            )
            meta = thaw(field.metadata)
            assert meta["statistics"] == {"over": "time", "operation": "instantaneous"}
            assert (
                not meta.get("statistical_interval")
                and meta["source_unit"] == CASES[name][-1]
            )
            var = next(
                v
                for v in dataset.data_vars.values()
                if v.attrs["cedarkit_parameter_id"] == identity["parameter"]
            )
            assert var.attrs["units"] == CASES[name][-1]
            selected = (
                var.sel(height_above_ground=2)
                if "height_above_ground" in var.dims
                else var
            )
            np.testing.assert_allclose(
                selected.values.reshape(-1),
                [0, np.nan, -1.25, 2.5],
                rtol=0,
                atol=0,
                equal_nan=True,
            )
        assert (
            len(
                source.sel(
                    parameter="h", member=member, level_type="pressure", level=600
                ).all()
            )
            == 0
        )
        with pytest.raises(CompletenessError):
            source.sel(queries).all(completeness="required")


@pytest.mark.parametrize("system", ["GEPS", "REPS"])
@pytest.mark.parametrize("member,hour", [(2, 0), (7, 0), (2, 18), (7, 18)])
def test_local_and_terrain_forms_cover_roles_without_sample_member_limits(
    tmp_path, system, member, hour
):
    path = tmp_path / "local.grib2"
    for name in ["cdbz", "dcape"] + (["zs"] if system == "GEPS" else []):
        encoded(path, name, member, hour, system=system)
        with from_source(
            {"kind": "file", "dataset": "CMA-" + system, "path": str(path)}
        ) as source:
            field = source.sel(parameter=name, member=member, **carrier(name)).one()
            assert field.identity.to_dict()["member"] == member
            ds = field.to_xarray()
            np.testing.assert_allclose(
                next(iter(ds.data_vars.values())).values.reshape(-1),
                [0, np.nan, -1.25, 2.5],
                equal_nan=True,
            )
            if name == "zs":
                meta = thaw(field.metadata)
                assert (
                    meta["native_fields"]["units"] == "m"
                    and meta["native_fields"]["parameterUnits"] == "gpm"
                )
                assert (
                    meta["source_unit"] == "Gpm"
                    and "producer" in meta["source_unit_basis"]["origin"]
                )


@pytest.mark.parametrize("system", ["GEPS", "REPS"])
@pytest.mark.parametrize(
    "changes",
    [
        {"centre": 98},
        {"localTablesVersion": 2},
        {"typeOfFirstFixedSurface": 100},
        {"typeOfEnsembleForecast": 1},
        {"significanceOfReferenceTime": 3},
        {"numberOfForecastsInEnsemble": 2},
    ],
)
def test_unreviewed_local_native_contexts_are_not_read_as_cdbz(
    tmp_path, system, changes
):
    path = tmp_path / "other.grib2"
    encoded(path, "cdbz", 7, 18, system=system, **changes)
    with from_source(
        {"kind": "file", "dataset": "CMA-" + system, "path": str(path)}
    ) as source:
        assert len(source.sel(parameter="cdbz", member=7, **carrier("cdbz")).all()) == 0


@pytest.mark.parametrize("system", ["GEPS", "REPS"])
def test_explicit_units_still_reject_conflicting_decoder_view(
    tmp_path, system, monkeypatch
):
    from reki.translation import grib_backend

    path = tmp_path / "conflict.grib2"
    encoded(path, "h", 5, 18, system=system)
    original = grib_backend._metadata

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        if "units" in result:
            result["units"] = "m/s"
        return result

    monkeypatch.setattr(grib_backend, "_metadata", changed)
    with from_source(
        {"kind": "file", "dataset": "CMA-" + system, "path": str(path)}
    ) as source:
        with pytest.raises(SourceError) as exc:
            source.sel(parameter="h", member=5, level_type="pressure").one()
        assert exc.value.context["reason"] == "inconsistent_native_metadata"


@pytest.mark.parametrize(
    "system,name",
    [
        ("GEPS", "sweatidx"),
        ("REPS", "pwat"),
        ("REPS", "zs"),
        ("REPS", "q"),
        ("REPS", "ps"),
    ],
)
def test_unresolved_product_bindings_keep_mapping_coverage_gap(tmp_path, system, name):
    path = tmp_path / "empty.grib2"
    path.touch()
    with (
        from_source(
            {"kind": "file", "dataset": "CMA-" + system, "path": str(path)}
        ) as source,
        pytest.raises(QueryError),
    ):
        source.sel(parameter=name, member=5).explain()


@pytest.mark.parametrize("system", ["GEPS", "REPS"])
def test_local_member_time_identity_crosses_month_without_a_lead_limit(
    tmp_path, system
):
    path = tmp_path / "month-boundary.grib2"
    encoded(path, "cdbz", 7, 18, system=system, dataDate=20261031)
    expected = "2026-11-01T06:00:00" if system == "GEPS" else "2026-11-01T00:00:00"
    with from_source(
        {"kind": "file", "dataset": "CMA-" + system, "path": str(path)}
    ) as source:
        field = source.sel(
            parameter="cdbz", member=7, valid_time=expected + "Z", **carrier("cdbz")
        ).one()
        assert field.identity.to_dict()["valid_time"] == expected + "Z"
        dataset = field.to_xarray()
        assert dataset.valid_time.item() == np.datetime64(expected, "ns").item()
        assert dataset.step.values.tolist() == [
            int(np.timedelta64(18, "h") / np.timedelta64(1, "ns"))
        ]
