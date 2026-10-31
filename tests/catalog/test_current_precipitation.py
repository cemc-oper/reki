"""Generated deterministic accumulation fields; real business evidence is separate."""

from datetime import datetime, timedelta, timezone

import eccodes
import numpy as np
import pytest

from cedarkit_query import CompletenessError, QueryError, SourceError
from reki import from_source
from reki.catalog.model import thaw

PARAMETERS = [
    ("CMA-GFS", "rain", 8),
    ("CMA-GFS", "rainc", 10),
    ("CMA-GFS", "rainnc", 9),
    ("CMA-MESO-3KM", "rain", 8),
    ("CMA-MESO-1KM", "rain", 8),
    ("CMA-TYM", "rain", 8),
    ("CMA-TYM", "rainc", 10),
    ("CMA-TYM", "rainnc", 9),
]
SYSTEMS = ["CMA-GFS", "CMA-MESO-3KM", "CMA-MESO-1KM", "CMA-TYM"]


def encoded(path, hour, number=8, values=None, minute_encoding=False, **overrides):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = eccodes.codes_grib_new_from_samples("regular_ll_sfc_grib2")
    try:
        date = overrides.get("dataDate", 20261030)
        time = overrides.get("dataTime", 0)
        end = datetime.strptime(f"{date:08d}{time:04d}", "%Y%m%d%H%M").replace(
            tzinfo=timezone.utc
        ) + timedelta(hours=hour)
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
            typeOfProcessedData=0 if hour == 0 else 1,
            typeOfGeneratingProcess=0 if hour == 0 else 2,
            significanceOfReferenceTime=0 if hour == 0 else 1,
            productDefinitionTemplateNumber=8,
            discipline=0,
            parameterCategory=1,
            parameterNumber=number,
            typeOfFirstFixedSurface=1,
            typeOfSecondFixedSurface=255,
            dataDate=20261030,
            dataTime=0,
            indicatorOfUnitOfTimeRange=0 if minute_encoding else 1,
            forecastTime=0,
        )
        native.update(overrides)
        if native["productDefinitionTemplateNumber"] in [8, 11]:
            descriptors = dict(
                numberOfTimeRange=1,
                typeOfTimeIncrement=2,
                typeOfStatisticalProcessing=1,
                indicatorOfUnitForTimeRange=0 if minute_encoding else 1,
                lengthOfTimeRange=hour * 60 if minute_encoding else hour,
                yearOfEndOfOverallTimeInterval=end.year,
                monthOfEndOfOverallTimeInterval=end.month,
                dayOfEndOfOverallTimeInterval=end.day,
                hourOfEndOfOverallTimeInterval=end.hour,
                minuteOfEndOfOverallTimeInterval=0,
                secondOfEndOfOverallTimeInterval=0,
            )
            descriptors.update({k: v for k, v in overrides.items() if k in descriptors})
            native.update(descriptors)
        for key, value in native.items():
            eccodes.codes_set(handle, key, value)
        eccodes.codes_set_values(
            handle,
            [0.0] * 4
            if values is None and hour == 0
            else [1.0, 2.0, 3.0, 4.0]
            if values is None
            else values,
        )
        with path.open("wb") as stream:
            eccodes.codes_write(handle, stream)
    finally:
        eccodes.codes_release(handle)


def local_path(root, system, hour):
    if system == "CMA-GFS":
        return (
            root
            / f"DATA/NAFP/NMC/GRAPES-GFS-GLB/2026/20261030/Z_NAFP_C_BABJ_20261030000000_P_NWPC-GRAPES-GFS-GLB-{hour:03}00.grib2"
        )
    if system == "CMA-MESO-1KM":
        return (
            root
            / f"DATA/NAFP/CEMC/MESO_1KM/ORI/2026/20261030/Z_NAFP_C_BABJ_20261030000000_P_CEMC-CMA-MESO-1KM-ORIG-{hour:03}00.grb2"
        )
    if system == "CMA-TYM":
        return (
            root
            / f"DATA/NAFP/NMC/GRAPES-TYM/2026/20261030/Z_NAFP_C_BABJ_20261030000000_P_NWPC-GRAPES-TYM-ACWP-{hour:03}00.grib2"
        )
    return (
        root
        / f"DATA/NAFP/GRAPES/RAFS/2026/20261030/Z_NAFP_C_BABJ_20261030000000_P_NWPC-GRAPES-3KM-ORIG-{hour:03}00.grb2"
    )


@pytest.mark.parametrize("system,name,number", PARAMETERS)
@pytest.mark.parametrize("hour", [0, 6, 24])
def test_public_current_accumulation_preserves_units_period_and_no_member(
    tmp_path, system, name, number, hour
):
    hour = 12 if system == "CMA-MESO-1KM" and hour == 24 else hour
    encoded(
        local_path(tmp_path, system, hour),
        hour,
        number,
        minute_encoding=system == "CMA-MESO-1KM",
    )
    with from_source(
        {"kind": "local", "dataset": system, "root": str(tmp_path)}
    ) as source:
        alias = {"rain": "APCP", "rainc": "ACPCP", "rainnc": "NCPCP"}[name]
        selected = source.sel(
            parameter=alias, time="2026-10-30T00:00:00Z", step=f"PT{hour}H"
        )
        field = selected.one()
        identity, metadata = field.identity.to_dict(), thaw(field.metadata)
        assert identity["parameter"] == "cedarkit." + name + ".since-initialization"
        assert "member" not in identity and "member_role" not in identity
        assert metadata["statistics"] == {
            "over": "time",
            "operation": "accumulation",
            "period": {"kind": "since_initialization"},
        }
        assert metadata["statistical_interval"] == {
            "start": identity["time"],
            "end": identity["valid_time"],
        }
        assert metadata["source_unit"] == "kg/m2" and metadata["unit"] == "mm"
        assert metadata["quantity_kind"] == "water_equivalent_precipitation"
        if system == "CMA-MESO-1KM":
            assert metadata["native_fields"]["indicatorOfUnitOfTimeRange"] == 0
            assert metadata["native_fields"]["indicatorOfUnitForTimeRange"] == 0
            assert metadata["native_fields"]["lengthOfTimeRange"] == hour * 60
        ds = selected.all().to_xarray()
        assert "member" not in ds.dims
        assert ds[name].attrs["units"] == "mm"
        np.testing.assert_array_equal(
            ds[name].values.reshape(-1),
            [0.0] * 4 if hour == 0 else [1.0, 2.0, 3.0, 4.0],
        )
        with pytest.raises(CompletenessError):
            selected.all(completeness="required")


@pytest.mark.parametrize("system", SYSTEMS)
@pytest.mark.parametrize(
    "native,reason",
    [
        ({"forecastTime": 3, "lengthOfTimeRange": 3}, "fixed_definition_mismatch"),
        ({"lengthOfTimeRange": 7}, "inconsistent_native_metadata"),
        ({"typeOfStatisticalProcessing": 0}, "fixed_definition_mismatch"),
        ({"numberOfTimeRange": 2}, "unsupported_native_encoding"),
        ({"typeOfTimeIncrement": 1}, "unsupported_native_encoding"),
    ],
)
def test_current_precipitation_does_not_hide_interval_errors(
    tmp_path, system, native, reason
):
    path = tmp_path / "bad-interval.grib2"
    if system == "CMA-MESO-1KM":
        native = {
            k: v * 60 if k in {"forecastTime", "lengthOfTimeRange"} else v
            for k, v in native.items()
        }
    encoded(path, 6, minute_encoding=system == "CMA-MESO-1KM", **native)
    with from_source({"kind": "file", "dataset": system, "path": str(path)}) as source:
        with pytest.raises(SourceError) as error:
            source.sel(parameter="rain", step="PT6H").one()
        assert error.value.context["reason"] == reason


@pytest.mark.parametrize("system", SYSTEMS)
def test_current_precipitation_does_not_override_native_unit_conflicts(
    tmp_path, monkeypatch, system
):
    from reki.translation import grib_backend

    path = tmp_path / "unit-conflict.grib2"
    encoded(path, 6, minute_encoding=system == "CMA-MESO-1KM")
    original = grib_backend._metadata

    def conflict(*args, **kwargs):
        result = original(*args, **kwargs)
        if result.get("productDefinitionTemplateNumber") == 8:
            result["units"] = "m"
        return result

    monkeypatch.setattr(grib_backend, "_metadata", conflict)
    with from_source({"kind": "file", "dataset": system, "path": str(path)}) as source:
        with pytest.raises(SourceError) as error:
            source.sel(parameter="rain", step="PT6H").one()
        assert error.value.context["reason"] == "inconsistent_native_metadata"


@pytest.mark.parametrize("system", SYSTEMS)
def test_current_precipitation_preserves_bitmap(tmp_path, system):
    path = tmp_path / "bitmap.grib2"
    encoded(
        path,
        6,
        values=[0, 9999, 1.25, 2.5],
        minute_encoding=system == "CMA-MESO-1KM",
        bitmapPresent=1,
        missingValue=9999,
    )
    with from_source({"kind": "file", "dataset": system, "path": str(path)}) as source:
        ds = source.sel(parameter="rain", step="PT6H").one().to_xarray()
        np.testing.assert_allclose(
            ds.rain.values.reshape(2, 2),
            [[0, np.nan], [1.25, 2.5]],
            rtol=0,
            atol=0,
            equal_nan=True,
        )


@pytest.mark.parametrize("system", SYSTEMS)
def test_current_precipitation_does_not_widen_definition_or_provision(tmp_path, system):
    path = tmp_path / "unopened"
    path.touch()
    with from_source({"kind": "file", "dataset": system, "path": str(path)}) as source:
        for query in [
            {
                "parameter": "rain",
                "step": "PT24H" if system == "CMA-MESO-1KM" else "PT9H",
            },
            {"parameter": "cedarkit.rain"},
            {"parameter": "rain", "level_type": "pressure", "level": 850},
            {
                "parameter": "rain",
                "statistics": {
                    "over": "time",
                    "operation": "accumulation",
                    "period": {"kind": "trailing", "duration": "PT6H"},
                },
            },
        ]:
            with pytest.raises(QueryError):
                source.sel(query).explain()
        if system in ["CMA-MESO-3KM", "CMA-MESO-1KM"]:
            for name in ["rainc", "rainnc"]:
                with pytest.raises(QueryError):
                    source.sel(parameter=name).explain()
        if system == "CMA-MESO-1KM":
            with pytest.raises(QueryError):
                source.sel(parameter="t2m", step="PT12H").explain()


@pytest.mark.parametrize("system", SYSTEMS)
def test_current_precipitation_keeps_other_templates_outside_its_mapping(
    tmp_path, system
):
    path = tmp_path / "instantaneous.grib2"
    encoded(path, 6, productDefinitionTemplateNumber=0)
    with from_source({"kind": "file", "dataset": system, "path": str(path)}) as source:
        with pytest.raises(QueryError) as error:
            source.sel(parameter="rain", step="PT6H").one()
        assert error.value.code == "no_match"


@pytest.mark.parametrize("system", ["CMA-MESO-1KM", "CMA-TYM"])
@pytest.mark.parametrize(
    "key",
    ["typeOfProcessedData", "typeOfGeneratingProcess", "significanceOfReferenceTime"],
)
def test_current_precipitation_keeps_analysis_markers_out_of_forecast(
    tmp_path, system, key
):
    path = tmp_path / "wrong-phase.grib2"
    encoded(path, 6, minute_encoding=system == "CMA-MESO-1KM", **{key: 0})
    with from_source({"kind": "file", "dataset": system, "path": str(path)}) as source:
        with pytest.raises(QueryError) as error:
            source.sel(parameter="rain", step="PT6H").one()
        assert error.value.code == "no_match"


@pytest.mark.parametrize("minute_encoding", [False, True])
def test_meso1_precipitation_accepts_equivalent_coded_time_units(
    tmp_path, minute_encoding
):
    path = tmp_path / "time-units.grib2"
    encoded(path, 6, minute_encoding=minute_encoding)
    with from_source(
        {"kind": "file", "dataset": "CMA-MESO-1KM", "path": str(path)}
    ) as source:
        field = source.sel(parameter="rain", step="PT6H").one()
        identity, meta = field.identity.to_dict(), thaw(field.metadata)
        assert identity["step"] == "PT21600S"
        assert identity["valid_time"] == "2026-10-30T06:00:00Z"
        assert meta["native_fields"]["lengthOfTimeRange"] == (
            360 if minute_encoding else 6
        )
        assert meta["statistical_interval"] == {
            "start": "2026-10-30T00:00:00Z",
            "end": "2026-10-30T06:00:00Z",
        }


LEAD_HOURS = {
    "CMA-GFS": [3, 12, 48, 72],
    "CMA-MESO-3KM": [1, 3, 12, 36],
    "CMA-MESO-1KM": [1, 3],
    "CMA-TYM": [3, 12, 48, 72],
    "CMA-GEPS": [12, 48, 72],
    "CMA-REPS": [12, 48, 72],
}
LEAD_CASES = [
    (system, name, number, member)
    for system, quantities in [
        ("CMA-GFS", [("rain", 8), ("rainc", 10), ("rainnc", 9)]),
        ("CMA-MESO-3KM", [("rain", 8)]),
        ("CMA-MESO-1KM", [("rain", 8)]),
        ("CMA-TYM", [("rain", 8), ("rainc", 10), ("rainnc", 9)]),
        ("CMA-GEPS", [("rain", 8), ("rainc", 10), ("rainnc", 9)]),
        ("CMA-REPS", [("rain", 8), ("rainc", 10)]),
    ]
    for name, number in quantities
    for member in ([0, 1, 2] if system in ["CMA-GEPS", "CMA-REPS"] else [None])
]


def lead_path(root, system, hour, member=None, reference=None):
    reference = reference or datetime(2026, 10, 30, 23, tzinfo=timezone.utc)
    layout = {
        "CMA-GFS": ("DATA/NAFP/NMC/GRAPES-GFS-GLB", "NWPC-GRAPES-GFS-GLB", "grib2"),
        "CMA-MESO-3KM": ("DATA/NAFP/GRAPES/RAFS", "NWPC-GRAPES-3KM-ORIG", "grb2"),
        "CMA-MESO-1KM": (
            "DATA/NAFP/CEMC/MESO_1KM/ORI",
            "CEMC-CMA-MESO-1KM-ORIG",
            "grb2",
        ),
        "CMA-TYM": ("DATA/NAFP/NMC/GRAPES-TYM", "NWPC-GRAPES-TYM-ACWP", "grib2"),
        "CMA-GEPS": ("DATA/NAFP/NMC/GRAPES-GEPS", "NWPC-GRAPES-GEPS-GLB", "grib2"),
        "CMA-REPS": ("ORIG-DATA/NAFP/CMA-REPS", "NWPC-GRAPES-REPS-CN", "grib2"),
    }
    base, prefix, suffix = layout[system]
    directory = reference + timedelta(hours=8) if system == "CMA-REPS" else reference
    tail = f"-m{member:03}" if member is not None else ""
    return (
        root
        / base
        / directory.strftime("%Y/%Y%m%d")
        / (
            f"Z_NAFP_C_BABJ_{reference:%Y%m%d%H%M%S}_P_{prefix}-{hour:03}00{tail}.{suffix}"
        )
    )


def encode_lead(path, system, hour, number=8, member=None, reference=None, **overrides):
    reference = reference or datetime(2026, 10, 30, 23, tzinfo=timezone.utc)
    native = {
        "dataDate": int(reference.strftime("%Y%m%d")),
        "dataTime": reference.hour * 100,
    }
    if member is not None:
        native.update(
            productDefinitionTemplateNumber=11,
            typeOfProcessedData=3 if member == 0 else 4,
            typeOfGeneratingProcess=4,
            significanceOfReferenceTime=1,
            typeOfEnsembleForecast=0 if member == 0 else 3 if member % 2 else 2,
            perturbationNumber=member,
            numberOfForecastsInEnsemble=0 if system == "CMA-REPS" else 31,
        )
    native.update(overrides)
    encoded(path, hour, number, minute_encoding=system == "CMA-MESO-1KM", **native)


@pytest.mark.parametrize("system,name,number,member", LEAD_CASES)
def test_extended_precipitation_valid_time_query_keeps_interval_units_and_roles(
    tmp_path, system, name, number, member
):
    hour = LEAD_HOURS[system][0]
    path = lead_path(tmp_path, system, hour, member)
    encode_lead(path, system, hour, number, member)
    reference = datetime(2026, 10, 30, 23, tzinfo=timezone.utc)
    q = {
        "parameter": {"rain": "APCP", "rainc": "ACPCP", "rainnc": "NCPCP"}[name],
        "time": reference.isoformat(),
        "valid_time": (reference + timedelta(hours=hour)).isoformat(),
    }
    if member is not None:
        q["member"] = member
    with from_source(
        {"kind": "local", "dataset": system, "root": str(tmp_path)}
    ) as source:
        field = source.sel(q).one()
        identity = field.identity.to_dict()
        meta = thaw(field.metadata)
        assert identity["step"] == f"PT{hour * 3600}S"
        assert meta["statistical_interval"] == {
            "start": identity["time"],
            "end": identity["valid_time"],
        }
        assert meta["source_unit"] == "kg/m2" and meta["unit"] == "mm"
        assert meta["statistics"]["period"] == {"kind": "since_initialization"}
        assert meta["native_fields"]["lengthOfTimeRange"] == hour * (
            60 if system == "CMA-MESO-1KM" else 1
        )
        if member is None:
            assert "member" not in identity
        else:
            assert identity["member"] == member
            assert identity["member_role"] == (
                "control" if member == 0 else "perturbation"
            )
            assert meta["native_fields"]["numberOfForecastsInEnsemble"] == (
                0 if system == "CMA-REPS" else 31
            )
        ds = field.to_xarray()
        assert ds[name].attrs["units"] == "mm"
        np.testing.assert_array_equal(ds[name].values.reshape(-1), [1, 2, 3, 4])


@pytest.mark.parametrize("system", LEAD_HOURS)
def test_old_and_extended_precipitation_rows_compose_without_ambiguity(
    tmp_path, system
):
    member = 0 if system in ["CMA-GEPS", "CMA-REPS"] else None
    hours = sorted({6, LEAD_HOURS[system][0], LEAD_HOURS[system][-1]})
    for hour in hours:
        encode_lead(
            lead_path(tmp_path, system, hour, member), system, hour, member=member
        )
    q = {
        "parameter": "rain",
        "time": "2026-10-30T23:00:00Z",
        "step": [f"PT{h}H" for h in hours],
    }
    if member is not None:
        q["member"] = member
    with from_source(
        {"kind": "local", "dataset": system, "root": str(tmp_path)}
    ) as source:
        fields = source.sel(q).all()
        assert len(fields) == len(hours)
        assert {f.identity.to_dict()["step"] for f in fields} == {
            f"PT{h * 3600}S" for h in hours
        }
        ds = fields.to_xarray()
        assert ds.sizes["step"] == len(hours)
        assert set(np.unique(ds.rain.values)) == {1, 2, 3, 4}
        with pytest.raises(CompletenessError):
            source.sel(q).all(completeness="required")


@pytest.mark.parametrize("system", LEAD_HOURS)
def test_precipitation_scope_extension_does_not_extend_instantaneous_pairs(
    tmp_path, system
):
    path = tmp_path / "unopened"
    path.touch()
    q = {"parameter": "t2m", "step": f"PT{LEAD_HOURS[system][0]}H"}
    if system in ["CMA-GEPS", "CMA-REPS"]:
        q["member"] = 0
    with from_source({"kind": "file", "dataset": system, "path": str(path)}) as source:
        with pytest.raises(QueryError):
            source.sel(q).explain()


@pytest.mark.parametrize("system", LEAD_HOURS)
def test_extended_precipitation_rejects_reanchored_window(tmp_path, system):
    hour = LEAD_HOURS[system][-1]
    member = 0 if system in ["CMA-GEPS", "CMA-REPS"] else None
    factor = 60 if system == "CMA-MESO-1KM" else 1
    path = tmp_path / "window.grib2"
    encode_lead(
        path,
        system,
        hour,
        member=member,
        forecastTime=factor,
        lengthOfTimeRange=(hour - 1) * factor,
    )
    q = {"parameter": "rain", "step": f"PT{hour}H"}
    if member is not None:
        q["member"] = member
    with from_source({"kind": "file", "dataset": system, "path": str(path)}) as source:
        with pytest.raises(SourceError) as error:
            source.sel(q).one()
        assert error.value.context["reason"] == "fixed_definition_mismatch"


@pytest.mark.parametrize("system", ["CMA-GFS", "CMA-REPS"])
def test_extended_precipitation_crosses_year_without_using_valid_date_directory(
    tmp_path, system
):
    reference = datetime(2026, 12, 31, 23, tzinfo=timezone.utc)
    member = 0 if system == "CMA-REPS" else None
    path = lead_path(tmp_path, system, 72, member, reference)
    encode_lead(path, system, 72, member=member, reference=reference)
    q = {
        "parameter": "rain",
        "time": reference.isoformat(),
        "valid_time": "2027-01-03T23:00:00Z",
    }
    if member is not None:
        q["member"] = member
    with from_source(
        {"kind": "local", "dataset": system, "root": str(tmp_path)}
    ) as source:
        field = source.sel(q).one()
        assert field.identity.to_dict()["valid_time"] == "2027-01-03T23:00:00Z"
        np.testing.assert_array_equal(
            field.to_xarray().rain.values.reshape(-1), [1, 2, 3, 4]
        )


@pytest.mark.parametrize("system", ["CMA-GFS", "CMA-GEPS"])
def test_extended_precipitation_retains_unit_conflict_diagnostics(
    tmp_path, monkeypatch, system
):
    from reki.translation import grib_backend

    path = tmp_path / "bad-unit.grib2"
    member = 0 if system == "CMA-GEPS" else None
    encode_lead(path, system, 72, member=member)
    original = grib_backend._metadata

    def conflict(*args, **kwargs):
        result = original(*args, **kwargs)
        if result.get("parameterCategory") == 1 and result.get("parameterNumber") == 8:
            result["units"] = "m"
        return result

    monkeypatch.setattr(grib_backend, "_metadata", conflict)
    q = {"parameter": "rain", "step": "PT72H"}
    if member is not None:
        q["member"] = member
    with from_source({"kind": "file", "dataset": system, "path": str(path)}) as source:
        with pytest.raises(SourceError) as error:
            source.sel(q).one()
        assert error.value.context["reason"] == "inconsistent_native_metadata"


@pytest.mark.parametrize("system", ["CMA-GFS", "CMA-GEPS"])
def test_extended_precipitation_preserves_nontrivial_bitmap(tmp_path, system):
    path = tmp_path / "bitmap.grib2"
    member = 0 if system == "CMA-GEPS" else None
    encode_lead(
        path,
        system,
        72,
        member=member,
        values=[0, 9999, 1.25, 2.5],
        bitmapPresent=1,
        missingValue=9999,
    )
    q = {"parameter": "rain", "step": "PT72H"}
    if member is not None:
        q["member"] = member
    with from_source({"kind": "file", "dataset": system, "path": str(path)}) as source:
        ds = source.sel(q).one().to_xarray()
        np.testing.assert_allclose(
            ds.rain.values.reshape(2, 2),
            [[0, np.nan], [1.25, 2.5]],
            rtol=0,
            atol=0,
            equal_nan=True,
        )


@pytest.mark.parametrize(
    "system,expected",
    [
        ("CMA-GFS", [0, 6, 12, 24, 48, 72]),
        ("CMA-MESO-3KM", [0, 3, 6, 12, 24, 36]),
        ("CMA-GEPS", [0, 6, 24]),
        ("CMA-REPS", [0, 6, 24]),
    ],
)
def test_omitted_steps_keep_each_builtin_parameters_declared_domain(
    tmp_path, system, expected
):
    path = tmp_path / "unopened"
    path.touch()
    q = {"parameter": "t2m", "time": "2026-10-30T06:00:00Z"}
    if system in ["CMA-GEPS", "CMA-REPS"]:
        q["member"] = 0
    with from_source({"kind": "file", "dataset": system, "path": str(path)}) as source:
        queries = source.sel(q).explain().to_dict()["effective_queries"]
        assert len(queries) == 1
        assert queries[0]["query"]["step"] == [f"PT{h * 3600}S" for h in expected]


def test_implicit_parameter_steps_intersect_context_bounds(tmp_path):
    path = tmp_path / "unopened"
    path.touch()
    with from_source(
        {"kind": "file", "dataset": "CMA-GFS", "path": str(path)},
        context={"scope": {"step": ["PT3H", "PT6H"]}},
    ) as source:
        (query,) = (
            source.sel(parameter="t2m", time="2026-10-30T06:00:00Z")
            .explain()
            .to_dict()["effective_queries"]
        )
        assert query["query"]["step"] == "PT21600S"
        with pytest.raises(QueryError):
            source.sel(
                parameter="t2m", time="2026-10-30T06:00:00Z", step=["PT3H", "PT6H"]
            )


def test_omitted_steps_remain_parameter_specific_in_multi_parameter_queries(tmp_path):
    path = tmp_path / "unopened"
    path.touch()
    with from_source(
        {"kind": "file", "dataset": "CMA-GFS", "path": str(path)}
    ) as source:
        queries = (
            source.sel(parameter=["t2m", "rain"], time="2026-10-30T06:00:00Z")
            .explain()
            .to_dict()["effective_queries"]
        )
        steps = {q["query"]["parameter"]: q["query"]["step"] for q in queries}
        assert steps["cedarkit.t2m"] == [
            f"PT{h * 3600}S" for h in [0, 6, 12, 24, 48, 72]
        ]
        assert steps["cedarkit.rain.since-initialization"] == [
            f"PT{h * 3600}S" for h in [0, 3, 6, 12, 24, 48, 72]
        ]


@pytest.mark.parametrize(
    "time_query", [{"step": ["PT3H", "PT6H"]}, {"valid_time": "2026-10-30T09:00:00Z"}]
)
def test_explicit_or_time_derived_steps_are_not_pruned_to_supported_subset(
    tmp_path, time_query
):
    path = tmp_path / "unopened"
    path.touch()
    with from_source(
        {"kind": "file", "dataset": "CMA-GFS", "path": str(path)}
    ) as source:
        with pytest.raises(QueryError):
            source.sel(parameter="t2m", time="2026-10-30T06:00:00Z", **time_query)


def test_external_catalog_does_not_inherit_builtin_implicit_step_policy(tmp_path):
    import json
    from reki.catalog import load_catalog, plan_source_binding, current
    from reki.selection.core import construct_source
    from reki.translation.grib_backend import GribBackend

    catalog = load_catalog().to_dict()
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(catalog))
    dataset = next(d for d in catalog["datasets"] if d["id"] == "cma_gfs_gmf")
    from pathlib import Path

    profile = json.loads(
        (Path(current.__file__).with_name("builtin") / "current-gfs.json").read_text()
    )
    raw = tmp_path / "unopened"
    raw.touch()
    context = {
        "catalog": {"path": str(path)},
        "parameter_registry": profile["parameter_registry"],
        "mappings": dataset["mappings"],
    }
    configuration = plan_source_binding(
        {"kind": "file", "dataset": "CMA-GFS", "path": str(raw)},
        context=context,
        product="orig",
        product_version="current",
    )
    with construct_source(configuration, GribBackend(configuration)) as source:
        with pytest.raises(QueryError):
            source.sel(parameter="t2m", time="2026-10-30T06:00:00Z").explain()


def test_fluent_explicit_steps_refine_implicit_parameter_bounds(tmp_path):
    path = tmp_path / "unopened"
    path.touch()
    with from_source(
        {"kind": "file", "dataset": "CMA-GFS", "path": str(path)}
    ) as source:
        (query,) = (
            source.sel(parameter="t2m", time="2026-10-30T06:00:00Z")
            .sel(step="PT6H")
            .explain()
            .to_dict()["effective_queries"]
        )
        assert query["query"]["step"] == "PT21600S"
