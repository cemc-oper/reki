"""Finite GFS directional energy products never infer an instantaneous flux."""

from datetime import datetime, timedelta, timezone

import eccodes
import numpy as np
import pytest

from cedarkit_query import CompletenessError, QueryError, SourceError
from reki import from_source
from reki.catalog.model import thaw


def encoded(path, name, hour=6, *, values=(0, 1.25, -2.5, 3), **overrides):
    path.parent.mkdir(parents=True, exist_ok=True)
    g = eccodes.codes_grib_new_from_samples("regular_ll_sfc_grib2")
    try:
        end = datetime(2026, 10, 30, 6, tzinfo=timezone.utc) + timedelta(hours=hour)
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
            productDefinitionTemplateNumber=8,
            typeOfGeneratingProcess=0 if hour == 0 else 2,
            significanceOfReferenceTime=0 if hour == 0 else 1,
            discipline=0,
            parameterCategory=4 if name == "guswc" else 5,
            parameterNumber=53 if name == "guswc" else 8,
            typeOfFirstFixedSurface=1,
            typeOfSecondFixedSurface=255,
            dataDate=20261030,
            dataTime=600,
            indicatorOfUnitOfTimeRange=1,
            forecastTime=0,
            numberOfTimeRange=1,
            typeOfStatisticalProcessing=1,
            typeOfTimeIncrement=2,
            indicatorOfUnitForTimeRange=1,
            lengthOfTimeRange=hour,
            yearOfEndOfOverallTimeInterval=end.year,
            monthOfEndOfOverallTimeInterval=end.month,
            dayOfEndOfOverallTimeInterval=end.day,
            hourOfEndOfOverallTimeInterval=end.hour,
            minuteOfEndOfOverallTimeInterval=0,
            secondOfEndOfOverallTimeInterval=0,
        )
        native.update(overrides)
        for k, v in native.items():
            eccodes.codes_set(g, k, v)
        eccodes.codes_set_values(g, values)
        with path.open("wb") as stream:
            eccodes.codes_write(g, stream)
    finally:
        eccodes.codes_release(g)


@pytest.mark.parametrize("name", ["guswc", "gdlwc"])
@pytest.mark.parametrize("hour", [0, 6])
def test_public_gfs_energy_values_are_not_scaled_by_duration_or_direction(
    tmp_path, name, hour
):
    path = tmp_path / "energy.grib2"
    encoded(path, name, hour)
    with from_source(
        {"kind": "file", "dataset": "CMA-GFS", "path": str(path)}
    ) as source:
        field = source.sel(
            parameter=name + "-since-initialization", step=f"PT{hour}H"
        ).one()
        ds = field.to_xarray()
        np.testing.assert_array_equal(ds[name].values.reshape(-1), [0, 1.25, -2.5, 3])
        assert ds[name].attrs["units"] == "J/m2"
        meta = thaw(field.metadata)
        assert meta["source_unit"] == "J/m2"
        assert meta["native_fields"]["units"] == "J m**-2"
        assert meta["statistics"]["operation"] == "accumulation"
        assert meta["statistics"]["period"] == {"kind": "since_initialization"}
        assert "member" not in field.identity.to_dict()
        assert meta["statistical_interval"]["start"] == "2026-10-30T06:00:00Z"
        assert (
            meta["statistical_interval"]["end"]
            == field.identity.to_dict()["valid_time"]
        )
        with pytest.raises(CompletenessError):
            source.sel(parameter=name + "-since-initialization", step=f"PT{hour}H").all(
                completeness="required"
            )


@pytest.mark.parametrize("name", ["guswc", "gdlwc"])
@pytest.mark.parametrize(
    "overrides,reason",
    [
        ({"typeOfStatisticalProcessing": 0}, "fixed_definition_mismatch"),
        ({"forecastTime": 3, "lengthOfTimeRange": 3}, "fixed_definition_mismatch"),
        ({"lengthOfTimeRange": 5}, "inconsistent_native_metadata"),
        ({"typeOfTimeIncrement": 1}, "unsupported_native_encoding"),
    ],
)
def test_energy_rejects_mean_reanchored_or_invalid_intervals(
    tmp_path, name, overrides, reason
):
    path = tmp_path / "invalid.grib2"
    encoded(path, name, **overrides)
    with from_source(
        {"kind": "file", "dataset": "CMA-GFS", "path": str(path)}
    ) as source:
        with pytest.raises(SourceError) as error:
            source.sel(parameter=name + "-since-initialization", step="PT6H").one()
        assert error.value.context["reason"] == reason


@pytest.mark.parametrize("unit", ["W m**-2", "unknown"])
def test_energy_unit_conflicts_and_unavailable_units_are_not_silently_reinterpreted(
    tmp_path, monkeypatch, unit
):
    from reki.translation import grib_backend

    path = tmp_path / "unit.grib2"
    encoded(path, "guswc")
    original = grib_backend._metadata

    def metadata(handle, **kwargs):
        value = original(handle, **kwargs)
        value["units"] = unit
        return value

    monkeypatch.setattr(grib_backend, "_metadata", metadata)
    with from_source(
        {"kind": "file", "dataset": "CMA-GFS", "path": str(path)}
    ) as source:
        selection = source.sel(parameter="guswc-since-initialization", step="PT6H")
        if unit == "unknown":
            # A proven mapping source unit may fill a decoder absence placeholder.
            assert selection.one().to_xarray().guswc.attrs["units"] == "J/m2"
        else:
            with pytest.raises(SourceError) as error:
                selection.one()
            assert error.value.context["reason"] == "inconsistent_native_metadata"


def test_energy_preserves_a_real_bitmap_including_zero_and_signed_values(tmp_path):
    path = tmp_path / "bitmap.grib2"
    encoded(
        path, "gdlwc", values=[0, 9999, -1.25, 2.5], bitmapPresent=1, missingValue=9999
    )
    with from_source(
        {"kind": "file", "dataset": "CMA-GFS", "path": str(path)}
    ) as source:
        values = (
            source.sel(parameter="gdlwc-since-initialization", step="PT6H")
            .one()
            .to_xarray()
            .gdlwc.values
        )
        np.testing.assert_allclose(
            values.reshape(-1), [0, np.nan, -1.25, 2.5], rtol=0, atol=0, equal_nan=True
        )


@pytest.mark.parametrize(
    "query",
    [
        {"parameter": "guswc-since-initialization", "step": "PT12H"},
        {"parameter": "gdlwc-since-initialization", "level_type": "atmosphere_top"},
        {"parameter": "tuswc"},
        {"parameter": "hfx"},
    ],
)
def test_energy_scope_does_not_acquire_unreviewed_leads_layers_or_heat_products(
    tmp_path, query
):
    path = tmp_path / "unopened"
    path.touch()
    with from_source(
        {"kind": "file", "dataset": "CMA-GFS", "path": str(path)}
    ) as source:
        with pytest.raises(QueryError):
            source.sel(query).explain()


@pytest.mark.parametrize(
    "system", ["CMA-MESO-3KM", "CMA-MESO-1KM", "CMA-TYM", "CMA-GEPS", "CMA-REPS"]
)
def test_gfs_radiation_does_not_register_other_system_support(tmp_path, system):
    path = tmp_path / "unopened"
    path.touch()
    with from_source({"kind": "file", "dataset": system, "path": str(path)}) as source:
        with pytest.raises(QueryError):
            source.sel(parameter="guswc-since-initialization", step="PT6H").explain()
