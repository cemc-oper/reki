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
        end = datetime(2026, 10, 30, tzinfo=timezone.utc) + timedelta(hours=hour)
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
        if native["productDefinitionTemplateNumber"] == 8:
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
                "step": "PT24H" if system == "CMA-MESO-1KM" else "PT12H",
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
