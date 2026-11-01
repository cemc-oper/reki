"""Finite GFS radiation energy products never infer an instantaneous flux."""

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
        end = datetime(2026, 10, 30, 12, tzinfo=timezone.utc) + timedelta(hours=hour)
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
            localTablesVersion=1 if name == "gulwc" else 0,
            productionStatusOfProcessedData=0,
            typeOfProcessedData=0 if hour == 0 else 1,
            productDefinitionTemplateNumber=8,
            typeOfGeneratingProcess=0 if hour == 0 else 2,
            significanceOfReferenceTime=0 if hour == 0 else 1,
            discipline=0,
            parameterCategory={"guswc": 4, "gdlwc": 5, "gswc": 4, "gulwc": 5, "gsw": 4}[
                name
            ],
            parameterNumber={
                "guswc": 53,
                "gdlwc": 8,
                "gswc": 11,
                "gulwc": 224,
                "gsw": 9,
            }[name],
            typeOfFirstFixedSurface=1,
            typeOfSecondFixedSurface=255,
            dataDate=20261030,
            dataTime=1200,
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


@pytest.mark.parametrize("name", ["guswc", "gdlwc", "gswc", "gulwc", "gsw"])
@pytest.mark.parametrize("hour", [0, 6, 12, 24, 48, 72])
def test_public_gfs_energy_values_are_not_scaled_by_duration_or_direction(
    tmp_path, name, hour
):
    path = tmp_path / "energy.grib2"
    encoded(path, name, hour)
    with from_source(
        {"kind": "file", "dataset": "CMA-GFS", "path": str(path)}
    ) as source:
        field = source.sel(
            parameter=name + "-since-initialization",
            time="2026-10-30T12:00:00Z",
            valid_time=(
                datetime(2026, 10, 30, 12, tzinfo=timezone.utc) + timedelta(hours=hour)
            ).isoformat(),
        ).one()
        ds = field.to_xarray()
        np.testing.assert_array_equal(ds[name].values.reshape(-1), [0, 1.25, -2.5, 3])
        assert ds[name].attrs["units"] == "J/m2"
        meta = thaw(field.metadata)
        assert meta["source_unit"] == "J/m2"
        assert meta["native_fields"]["units"] == (
            "unknown" if name == "gulwc" else "J m**-2"
        )
        if name == "gsw":
            # A code-table annotation and a statistical unit concept have different roles.
            assert meta["native_fields"]["parameterUnits"] == "W m-2"
        if name == "gulwc":
            assert meta["native_fields"]["parameterUnits"] == "224"
        assert meta["statistics"]["operation"] == "accumulation"
        assert meta["statistics"]["period"] == {"kind": "since_initialization"}
        assert "member" not in field.identity.to_dict()
        assert meta["statistical_interval"]["start"] == "2026-10-30T12:00:00Z"
        assert field.identity.to_dict()["step"] == f"PT{hour * 3600}S"
        assert (
            meta["statistical_interval"]["end"]
            == field.identity.to_dict()["valid_time"]
        )
        with pytest.raises(CompletenessError):
            source.sel(parameter=name + "-since-initialization", step=f"PT{hour}H").all(
                completeness="required"
            )


@pytest.mark.parametrize("name", ["guswc", "gdlwc", "gswc", "gulwc", "gsw"])
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
@pytest.mark.parametrize("name", ["guswc", "gswc", "gulwc", "gsw"])
def test_energy_unit_conflicts_and_unavailable_units_are_not_silently_reinterpreted(
    tmp_path, monkeypatch, unit, name
):
    from reki.translation import grib_backend

    path = tmp_path / "unit.grib2"
    encoded(path, name)
    original = grib_backend._metadata

    def metadata(handle, **kwargs):
        value = original(handle, **kwargs)
        value["units"] = unit
        return value

    monkeypatch.setattr(grib_backend, "_metadata", metadata)
    with from_source(
        {"kind": "file", "dataset": "CMA-GFS", "path": str(path)}
    ) as source:
        selection = source.sel(parameter=name + "-since-initialization", step="PT6H")
        if unit == "unknown":
            # A proven mapping source unit may fill a decoder absence placeholder.
            assert selection.one().to_xarray()[name].attrs["units"] == "J/m2"
        else:
            with pytest.raises(SourceError) as error:
                selection.one()
            assert error.value.context["reason"] == "inconsistent_native_metadata"


@pytest.mark.parametrize("name", ["gdlwc", "gswc", "gulwc", "gsw"])
def test_energy_preserves_a_real_bitmap_including_zero_and_signed_values(
    tmp_path, name
):
    path = tmp_path / "bitmap.grib2"
    encoded(
        path, name, values=[0, 9999, -1.25, 2.5], bitmapPresent=1, missingValue=9999
    )
    with from_source(
        {"kind": "file", "dataset": "CMA-GFS", "path": str(path)}
    ) as source:
        values = (
            source.sel(parameter=name + "-since-initialization", step="PT6H")
            .one()
            .to_xarray()[name]
            .values
        )
        np.testing.assert_allclose(
            values.reshape(-1), [0, np.nan, -1.25, 2.5], rtol=0, atol=0, equal_nan=True
        )


@pytest.mark.parametrize(
    "query",
    [
        {"parameter": "guswc-since-initialization", "step": "PT9H"},
        {"parameter": "gdlwc-since-initialization", "level_type": "atmosphere_top"},
        {"parameter": "tuswc"},
        {"parameter": "tswc"},
        {"parameter": "tulwc"},
        {"parameter": "gswc-since-initialization", "step": "PT9H"},
        {"parameter": "gulwc-since-initialization", "step": "PT9H"},
        {"parameter": "hfx"},
        {"parameter": "gsw-since-initialization", "step": "PT9H"},
        {"parameter": "gsw-since-initialization", "level_type": "atmosphere_top"},
        {"parameter": "tsw"},
        {"parameter": "glw"},
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
@pytest.mark.parametrize("name", ["guswc", "gswc", "gulwc", "gsw"])
def test_gfs_radiation_does_not_register_other_system_support(tmp_path, system, name):
    path = tmp_path / "unopened"
    path.touch()
    with from_source({"kind": "file", "dataset": system, "path": str(path)}) as source:
        with pytest.raises(QueryError):
            source.sel(parameter=name + "-since-initialization", step="PT6H").explain()


@pytest.mark.parametrize("name", ["guswc", "gswc", "gulwc", "gsw"])
def test_energy_all_assembles_cross_day_and_month_steps_without_new_windows(
    tmp_path, name
):
    path = tmp_path / "cross-month.grib2"
    messages = []
    for hour in [12, 24, 48, 72]:
        encoded(path, name, hour, values=[hour, -hour, 0, hour + 0.5])
        messages.append(path.read_bytes())
    path.write_bytes(b"".join(messages))
    with from_source(
        {"kind": "file", "dataset": "CMA-GFS", "path": str(path)}
    ) as source:
        selected = source.sel(
            parameter=name + "-since-initialization",
            time="2026-10-30T12:00:00Z",
            step=["PT12H", "PT24H", "PT48H", "PT72H"],
        )
        fields = selected.all()
        assert len(fields) == 4
        ds = fields.to_xarray()
        assert ds.sizes["step"] == 4
        for hour, field in zip([12, 24, 48, 72], fields):
            identity = field.identity.to_dict()
            assert identity["valid_time"] == (
                datetime(2026, 10, 30, 12, tzinfo=timezone.utc) + timedelta(hours=hour)
            ).isoformat().replace("+00:00", "Z")
            np.testing.assert_array_equal(
                ds[name].sel(step=np.timedelta64(hour, "h")).values.reshape(-1),
                [hour, -hour, 0, hour + 0.5],
            )
        with pytest.raises(CompletenessError):
            selected.all(completeness="required")


@pytest.mark.parametrize(
    "name,changes",
    [
        ("gsw", {"parameterNumber": 11}),  # GSWC clear sky is distinct.
        ("gsw", {"parameterNumber": 229}),  # GNSW flux is distinct.
        ("gsw", {"parameterCategory": 5, "parameterNumber": 5}),  # Unresolved GLW.
        ("gsw", {"centre": 98}),
        ("gsw", {"tablesVersion": 5}),
        ("gsw", {"localTablesVersion": 1}),
        ("gsw", {"parameterNumber": 250}),
        ("gsw", {"typeOfFirstFixedSurface": 8}),
        ("gsw", {"typeOfGeneratingProcess": 0}),
        ("gsw", {"typeOfProcessedData": 0}),
        ("gsw", {"significanceOfReferenceTime": 0}),
        ("gswc", {"parameterNumber": 52}),  # GDSWC downwardSW is not GSWC netSW.
        ("gulwc", {"centre": 98}),
        ("gulwc", {"localTablesVersion": 0}),
        ("gulwc", {"parameterNumber": 225}),
        ("gulwc", {"typeOfGeneratingProcess": 0}),
        ("gulwc", {"typeOfFirstFixedSurface": 8}),
    ],
)
def test_new_energy_bindings_reject_other_identities_and_contexts(
    tmp_path, name, changes
):
    path = tmp_path / "wrong-context.grib2"
    encoded(path, name, **changes)
    with from_source(
        {"kind": "file", "dataset": "CMA-GFS", "path": str(path)}
    ) as source:
        with pytest.raises(QueryError) as error:
            source.sel(parameter=name + "-since-initialization", step="PT6H").one()
        assert error.value.code == "no_match"
