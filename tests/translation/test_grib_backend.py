"""Actual ecCodes I/O on disposable generated GRIB2; never business acceptance."""

import json
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pytest
import eccodes

from cedarkit_query import QueryError, SourceError
from reki import from_source
from reki.catalog import load_resource, plan_source_binding
from reki.diagnostics import collect_io_metrics
from reki.selection.core import construct_source
from reki.translation.grib_backend import GribBackend
from reki.translation.grib_mapping import _observed_units, named_branches


@pytest.fixture
def write_grib(tmp_path):
    def write(name="SYNTHETIC.grib2", records=None):
        path = tmp_path / name
        if records is None:
            records = [{}]
        with path.open("wb") as stream:
            for index, options in enumerate(records):
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
                        "typeOfFirstFixedSurface": 100,
                        "scaleFactorOfFirstFixedSurface": 0,
                        "scaledValueOfFirstFixedSurface": 85000,
                    }
                    settings.update({k: v for k, v in options.items() if k != "values"})
                    for key, value in settings.items():
                        eccodes.codes_set(handle, key, value)
                    eccodes.codes_set_values(
                        handle,
                        options.get(
                            "values", np.array([280.0, 281.0, 282.0, 283.0]) + index
                        ),
                    )
                    eccodes.codes_write(handle, stream)
                finally:
                    eccodes.codes_release(handle)
        return path

    return write


@pytest.fixture
def configured(write_grib):
    def make(records=None, *, business=False):
        path = write_grib(records=records)
        config = plan_source_binding({"kind": "file", "path": str(path)})
        return construct_source(config, GribBackend(config)), path, {}

    return make


def test_metadata_selection_is_lazy_and_values_coordinates_are_independent(
    configured, monkeypatch
):
    source, file, _ = configured()
    selected = source.sel(
        native={"grib": {"parameterNumber": 0}},
        level_type="pressure",
        level=85000,
        level_unit="Pa",
    )
    original = eccodes.codes_get_double_array
    loads = []

    def get_array(handle, key):
        if key == "values":
            loads.append(key)
        return original(handle, key)

    monkeypatch.setattr(eccodes, "codes_get_double_array", get_array)
    assert (
        selected.explain().analysis["translations"][0]["coverage"]["status"] == "passed"
    )
    assert not loads
    result = selected.all()
    assert len(result) == 1 and not loads
    assert (
        result.report.overall["status"] == "unchecked"
    )  # No independent business domain.
    assert result.report.context["source"]["fingerprints"][str(file)]
    ds = result.to_xarray(rename="raw")
    np.testing.assert_array_equal(
        ds.raw.values.reshape(2, 2), [[280.0, 281.0], [282.0, 283.0]]
    )
    assert ds.raw.dims == ("time", "step", "pressure", "latitude", "longitude")
    assert ds.pressure.values[0] == 850 and ds.raw.attrs["units"] == "K"
    assert len(loads) == 1
    source.close()
    assert ds.raw.values.flat[0] == 280.0
    with pytest.raises(SourceError):
        result.to_xarray(rename="raw")


def test_source_order_and_exact_record_dedup_across_duplicate_paths(
    configured, write_grib
):
    source, file, _ = configured([{}, {"scaledValueOfFirstFixedSurface": 50000}])
    config = replace(
        source.configuration, source={"kind": "file", "path": (str(file), str(file))}
    )
    source = construct_source(config, GribBackend(config))
    fields = source.sel(native={"grib": {"parameterNumber": 0}}).all()
    assert len(fields) == 2 and fields.first().identity.level == 850
    assert (
        source.sel(native={"grib": {"parameterNumber": 0}}).first().identity.level
        == 850
    )


@pytest.mark.parametrize("catalog_path", [False, True])
def test_local_named_query_discovers_all_member_mapping_branches(
    write_grib, tmp_path, catalog_path
):
    archive = tmp_path / "DATA/NAFP/NMC/GRAPES-GEPS/2026/20260101"
    archive.mkdir(parents=True)
    prefix = "Z_NAFP_C_BABJ_20260101000000_P_NWPC-GRAPES-GEPS-GLB-00600"
    paths = []
    for member, kind in ((0, 0), (1, 3), (2, 2)):
        record = {
            "centre": 38,
            "subCentre": 0,
            "tablesVersion": 4,
            "localTablesVersion": 0,
            "productDefinitionTemplateNumber": 1,
            "productionStatusOfProcessedData": 0,
            "typeOfGeneratingProcess": 4,
            "significanceOfReferenceTime": 1,
            "typeOfProcessedData": 3 if member == 0 else 4,
            "typeOfEnsembleForecast": kind,
            "perturbationNumber": member,
            "numberOfForecastsInEnsemble": 31,
            "values": np.full(4, 280.0 + member),
        }
        paths.append(write_grib(str(archive / f"{prefix}-m{member:03d}.grib2"), records=[record]))
    context = None
    if catalog_path:
        path = tmp_path / "catalog.json"
        catalog = load_resource({"builtin": "reki.catalog"}, "catalog")
        document = catalog.value.to_dict()
        dataset = next(row for row in document["datasets"] if row["id"] == "cma_geps")
        for ref in (dataset["parameter_registry"], dataset["mappings"]["grib2"]):
            if "path" in ref:
                resource = Path(ref["path"])
                (tmp_path / resource).write_bytes((catalog.base_dir / resource).read_bytes())
        path.write_text(json.dumps(document))
        context = {"catalog": {"path": str(path)}}
    with from_source(
        {"kind": "local", "dataset": "cma_geps", "root": str(tmp_path)}, context=context
    ) as source:
        fields = source.sel(
            parameter="cedarkit.t", time="2026-01-01T00:00:00Z", step="PT6H",
            level_type="pressure", level=85000, level_unit="Pa", member=[2, 1, 0],
        ).all()
        assert [field.identity.member for field in fields] == [0, 1, 2]
        assert list(fields.report.context["source"]["paths"]) == [str(path) for path in paths]
        ds = fields.to_xarray()
        assert ds.member_role.values.tolist() == ["control", "perturbation", "perturbation"]
        np.testing.assert_array_equal(
            ds.t.isel(time=0, step=0, pressure=0, latitude=0, longitude=0), [280, 281, 282]
        )


def test_file_replacement_fails_delayed_reference(configured, write_grib):
    source, file, _ = configured()
    field = source.sel(native={"grib": {"parameterNumber": 0}}).one()
    replacement = write_grib("replacement.grib2")
    replacement.replace(file)
    with pytest.raises(SourceError) as exc:
        field.to_xarray(rename="raw")
    assert exc.value.context["reason"] == "resource_changed"
    with pytest.raises(SourceError) as exc:
        field.read_grib_message()
    assert exc.value.context["reason"] == "resource_changed"


def test_repeated_native_keys_keep_individually_readable_messages(configured):
    source, path, _ = configured([{}, {}])
    original = path.read_bytes()
    with source:
        fields = source.sel(native={"grib": {"parameterNumber": 0}}).all()
        assert len(fields) == 2
        assert fields[0].identity == fields[1].identity
        offset = 0
        with collect_io_metrics() as metrics:
            for ordinal, field in enumerate(fields, 1):
                locator = field.metadata["source"]
                length = locator["length"]
                assert (locator["ordinal"], locator["offset"]) == (ordinal, offset)
                assert field.read_grib_message() == original[offset:offset + length]
                offset += length
            assert fields[0].read_grib_message() == original[:fields[0].metadata["source"]["length"]]
        assert metrics.snapshot()["file_open_count"] == 1
        assert offset == len(original)
    with pytest.raises(SourceError):
        fields[0].read_grib_message()


def test_native_query_does_not_fabricate_business_id(configured):
    source, _, _ = configured(business=False)
    field = source.sel(native={"grib": {"parameterNumber": 0}}).one()
    assert "parameter" not in field.identity.to_dict()
    ds = field.to_xarray(rename="native_temperature")
    assert "cedarkit_parameter_id" not in ds.native_temperature.attrs
    assert field.metadata["native_fields"]["units"] == "K"


def test_no_match_is_empty_but_truncated_stream_is_a_source_error(configured):
    source, file, _ = configured()
    assert (
        len(
            source.sel(
                native={"grib": {"parameterNumber": 0}},
                level_type="pressure",
                level=700,
            ).all()
        )
        == 0
    )
    payload = file.read_bytes()
    file.write_bytes(payload[:-16])
    with pytest.raises(SourceError) as exc:
        source.sel(native={"grib": {"parameterNumber": 0}}).all()
    assert exc.value.code == "decode_failed" and "report" not in exc.value.to_dict()


def test_fresh_public_file_pipeline_has_no_cfgrib_or_legacy_package_import(configured):
    import subprocess, sys

    _, file, context = configured()
    script = """import json,sys
from reki import from_source
with from_source({"kind":"file","path":sys.argv[1]},context=json.loads(sys.argv[2])) as source:
    ds=source.sel(native={"grib": {"parameterNumber": 0}}).one().to_xarray(rename="raw")
    assert ds.raw.values.flat[0]==280.
assert "cfgrib" not in sys.modules
assert "reki.readers.grib" not in sys.modules
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(file), json.dumps(context)],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_physical_file_aliases_keep_first_record_identity(configured):
    source, file, _ = configured()
    alias = file.parent / "SYNTHETIC-alias.grib2"
    alias.symlink_to(file)
    config = replace(
        source.configuration, source={"kind": "file", "path": (str(file), str(alias))}
    )
    fields = (
        construct_source(config, GribBackend(config))
        .sel(native={"grib": {"parameterNumber": 0}})
        .all()
    )
    assert len(fields) == 1


def test_shared_io_preserves_header_release_and_grib1_boundary(write_grib, tmp_path):
    from reki.grib_io import iter_headers, load_message_at_offset
    from reki.readers.grib.eccodes._scan import iter_headers as legacy_iter

    assert legacy_iter is iter_headers
    file = write_grib(records=[{}, {}])
    iterator = iter_headers(file)
    header = next(iterator)
    offset = header.offset
    iterator.close()
    assert header.handle is None
    handle = load_message_at_offset(file, offset)
    assert handle is not None
    eccodes.codes_release(handle)
    handle = eccodes.codes_grib_new_from_samples("regular_ll_sfc_grib1")
    file1 = tmp_path / "SYNTHETIC.grib1"
    try:
        with file1.open("wb") as stream:
            eccodes.codes_write(handle, stream)
    finally:
        eccodes.codes_release(handle)
    # Raw I/O is edition-independent; canonical GRIB1 interpretation is not claimed.
    iterator = iter_headers(file1)
    try:
        with next(iterator) as header:
            assert eccodes.codes_get_long(header.handle, "edition") == 1
    finally:
        iterator.close()


def test_bitmap_missing_cells_are_values_not_missing_records(configured):
    source, _, _ = configured(
        [
            {
                "bitmapPresent": 1,
                "missingValue": 9999.0,
                "values": [9999.0, 9999.0, 9999.0, 9999.0],
            }
        ]
    )
    fields = source.sel(native={"grib": {"parameterNumber": 0}}).all()
    assert len(fields) == 1 and fields.report.overall["field_count"] == 1
    assert fields.to_xarray(rename="raw").raw.isnull().all()


def test_named_original_values_keep_untranslated_surface_and_repeated_positions(
    write_grib, tmp_path
):
    settings = {
        "centre": 38,
        "discipline": 0,
        "parameterCategory": 7,
        "parameterNumber": 12,
        "typeOfFirstFixedSurface": 166,
        "bitmapPresent": 1,
        "missingValue": 9999.0,
        "values": [9999.0] * 4,
    }
    path = write_grib(records=[settings, {**settings, "values": [1.0, 2.0, 3.0, 4.0]}])
    source = {"kind": "file", "path": str(path), "dataset": "cma_meso_3km"}
    base = plan_source_binding(source)
    catalog_resource = load_resource(base.definitions[0]["reference"], "catalog")
    parameters = load_resource(
        base.definitions[1]["reference"], "parameters", base_dir=catalog_resource.base_dir
    ).value.to_dict()
    mappings = base.mappings[0].to_dict()
    catalog = catalog_resource.value.to_dict()
    pid = "cedarkit.ripbl"
    parameters["parameters"] = [row for row in parameters["parameters"] if row["parameter_id"] != pid]
    parameters["parameters"].append(
        {"parameter_id": pid, "name": "ripbl", "unit": "1", "fixed_conditions": {}}
    )
    mappings["mappings"] = [row for row in mappings["mappings"] if row["parameter_id"] != pid]
    mappings["mappings"].append(
        {
            "id": "ripbl.native",
            "parameter_id": pid,
            "backend": "grib2",
            "applies_to": {"dataset": source["dataset"], "product": "orig", "product_version": "current"},
            "when": {},
            "evidence": [],
            "native": {
                "match": {"edition": 2, "discipline": 0, "parameterCategory": 7,
                          "parameterNumber": 12, "productDefinitionTemplateNumber": 0,
                          "typeOfFirstFixedSurface": 166},
                "translate": {"time": {"rule": "grib.time"}},
            },
        }
    )
    dataset = next(row for row in catalog["datasets"] if row["id"] == source["dataset"])
    provides = dataset["products"][0]["provides"]
    if {"parameter": pid} not in provides:
        provides.append({"parameter": pid})
    for name, payload in (("catalog", catalog), ("parameters", parameters), ("mappings", mappings)):
        (tmp_path / f"{name}.json").write_text(json.dumps(payload))
    context = {
        "catalog": {"path": str(tmp_path / "catalog.json")},
        "parameter_registry": {"path": str(tmp_path / "parameters.json")},
        "mappings": {"grib2": {"path": str(tmp_path / "mappings.json")}},
    }
    with collect_io_metrics() as metrics, from_source(source, context=context) as owner:
        fields = owner.sel(parameter="ripbl", step="PT6H").all()
        assert len(fields) == 2 and fields[0].identity == fields[1].identity
        assert metrics.snapshot()["value_decode_count"] == 0
        assert fields[0].identity.native["grib"]["typeOfFirstFixedSurface"] == 166
        assert "level_type" not in fields[0].identity.to_dict()
        first, second = (field.read_grib_message() for field in fields)
        assert first != second and first + second == path.read_bytes()
        assert [field.metadata["source"]["offset"] for field in fields] == [0, len(first)]
        first_values, second_values = (field.to_xarray().ripbl for field in fields)
        assert first_values.isnull().all()
        assert "units" not in second_values.attrs
        np.testing.assert_array_equal(second_values.values.reshape(-1), [1.0, 2.0, 3.0, 4.0])


@pytest.mark.parametrize("first,second", [(1, 8), (8, 1)])
def test_named_mixed_layer_survives_encoded_selection_and_output(
    configured, first, second
):
    source, _, _ = configured(
        [{"typeOfFirstFixedSurface": first, "typeOfSecondFixedSurface": second}]
    )
    layer = {"bottom": {"type": "surface"}, "top": {"type": "atmosphere_top"}}
    fields = source.sel(native={"grib": {"parameterNumber": 0}}, layer=layer).all()
    assert len(fields) == 1 and fields[0].identity.to_dict()["layer"] == layer
    result = fields.to_xarray(rename="raw")
    assert len(result.data_vars) == 1
    variable = next(iter(result.data_vars.values()))
    assert variable.attrs["GRIB_typeOfFirstFixedSurface"] == first
    assert variable.attrs["GRIB_typeOfSecondFixedSurface"] == second
    assert result.sizes["latitude"] == result.sizes["longitude"] == 2


@pytest.mark.parametrize("template", [8, 11])
def test_encoded_signed_interval_start_has_nonnegative_result_step(
    configured, template
):
    source, _, _ = configured(
        [
            {
                "productDefinitionTemplateNumber": template,
                "forecastTime": -1,
                "numberOfTimeRange": 1,
                "typeOfTimeIncrement": 2,
                "indicatorOfUnitForTimeRange": 1,
                "lengthOfTimeRange": 1,
                "yearOfEndOfOverallTimeInterval": 2026,
                "monthOfEndOfOverallTimeInterval": 1,
                "dayOfEndOfOverallTimeInterval": 1,
                "hourOfEndOfOverallTimeInterval": 0,
                "minuteOfEndOfOverallTimeInterval": 0,
                "secondOfEndOfOverallTimeInterval": 0,
            }
        ],
        business=False,
    )
    fields = source.sel(
        native={"grib": {"productDefinitionTemplateNumber": template}}
    ).all()
    assert len(fields) == 1
    identity = fields[0].identity.to_dict()
    assert identity["time"] == identity["valid_time"] == "2026-01-01T00:00:00Z"
    assert (
        identity["step"] == "PT0S" and identity["native"]["grib"]["forecastTime"] == -1
    )
    assert len(fields.to_xarray(rename="synthetic_interval").data_vars) == 1


@pytest.mark.parametrize("window", [1, 2])
def test_named_trailing_window_checks_the_encoded_bounds(write_grib, tmp_path, window):
    path = write_grib(
        records=[
            {
                "productDefinitionTemplateNumber": 8,
                "centre": 38,
                "subCentre": 0,
                "tablesVersion": 4,
                "localTablesVersion": 0,
                "productionStatusOfProcessedData": 0,
                "significanceOfReferenceTime": 1,
                "typeOfProcessedData": 1,
                "typeOfGeneratingProcess": 2,
                "discipline": 0,
                "parameterCategory": 2,
                "parameterNumber": 2,
                "typeOfFirstFixedSurface": 103,
                "scaledValueOfFirstFixedSurface": 10,
                "forecastTime": 6 - window,
                "typeOfStatisticalProcessing": 2,
                "numberOfTimeRange": 1,
                "typeOfTimeIncrement": 2,
                "indicatorOfUnitForTimeRange": 1,
                "lengthOfTimeRange": window,
                "yearOfEndOfOverallTimeInterval": 2026,
                "monthOfEndOfOverallTimeInterval": 1,
                "dayOfEndOfOverallTimeInterval": 1,
                "hourOfEndOfOverallTimeInterval": 6,
                "minuteOfEndOfOverallTimeInterval": 0,
                "secondOfEndOfOverallTimeInterval": 0,
            }
        ]
    )
    source = {"kind": "file", "path": str(path), "dataset": "cma_meso_1km"}
    mappings = plan_source_binding(source).mappings[0].to_dict()
    row = next(r for r in mappings["mappings"] if r["id"] == "u10mmax-1.forecast")
    row["native"]["match"].pop("lengthOfTimeRange")
    resource = tmp_path / "trailing-mappings.json"
    resource.write_text(json.dumps(mappings))
    with from_source(
        source, context={"mappings": {"grib2": {"path": str(resource)}}}
    ) as owner:
        selection = owner.sel(
            parameter="cedarkit.u10mmax-1", time="2026-01-01T00:00:00Z", step="PT6H"
        )
        if window == 2:
            with pytest.raises(SourceError) as caught:
                selection.one()
            assert caught.value.context["reason"] == "fixed_definition_mismatch"
        else:
            field = selection.one()
            assert field.metadata["statistical_interval"] == {
                "start": "2026-01-01T05:00:00Z",
                "end": "2026-01-01T06:00:00Z",
            }


@pytest.mark.parametrize("missing_bound", [None, "time", "step", "forecastTime", "lengthOfTimeRange"])
def test_snow_diagnostic_unit_requires_pinned_encoded_bounds(tmp_path, missing_bound):
    config = plan_source_binding(
        {"kind": "file", "path": str(tmp_path / "reps.grib2"), "dataset": "cma_reps"}
    )
    query = {
        "parameter": "cedarkit.sf",
        "time": "2026-11-02T06:00:00Z",
        "step": "PT6H",
        "member": 2,
    }
    resource = config.mappings[0].to_dict()
    target = next(row for row in resource["mappings"] if row["id"] == "sf.diagnostic.forecast.negative.2026110206")
    if missing_bound is not None:
        for group in (target["applies_to"], target["when"], target["native"]["match"]):
            group.pop(missing_bound, None)
    mappings = {(resource["id"], row["id"]): row for row in resource["mappings"]}
    if missing_bound is None:
        branches = named_branches(query, 0, config, mappings)
        reviewed, = [branch for branch in branches if branch["basis"][0]["mapping"] == target["id"]]
        assert reviewed["candidate_filter"]["forecastTime"] == 0
        assert set(reviewed["candidate_filter"]["lengthOfTimeRange"]) == {6, 48}
        assert set(reviewed["candidate_filter"]["perturbationNumber"]) == {2, 14}
        assert "period" not in config.parameters["cedarkit.sf"]["fixed_conditions"]["statistics"]
    else:
        with pytest.raises(QueryError) as caught:
            named_branches(query, 0, config, mappings)
        assert caught.value.context["reason"] == "translation_unavailable"


@pytest.mark.parametrize(
    "settings,lat,lon",
    [
        ({}, [50, 49], [100, 101]),
        (
            {
                "iScansNegatively": 1,
                "longitudeOfFirstGridPointInDegrees": 101,
                "longitudeOfLastGridPointInDegrees": 100,
            },
            [50, 49],
            [101, 100],
        ),
        (
            {
                "jScansPositively": 1,
                "latitudeOfFirstGridPointInDegrees": 49,
                "latitudeOfLastGridPointInDegrees": 50,
            },
            [49, 50],
            [100, 101],
        ),
    ],
)
def test_supported_grid_records_raw_evidence_and_preserves_axes(
    configured, settings, lat, lon
):
    source, _, _ = configured([settings])
    with source:
        field = source.sel(native={"grib": {"parameterNumber": 0}}).one()
        raw = field.metadata["native_fields"]
        assert raw["Ni"] == raw["Nj"] == 2
        assert raw["numberOfDataPoints"] == 4
        assert raw["gridDefinitionTemplateNumber"] == 0
        assert raw["scanningMode"] >= 0
        ds = field.to_xarray(rename="raw")
        np.testing.assert_array_equal(ds.latitude, lat)
        np.testing.assert_array_equal(ds.longitude, lon)
        np.testing.assert_array_equal(
            ds.raw.values.reshape(2, 2), [[280, 281], [282, 283]]
        )


def test_unregistered_native_codes_and_unmasked_sentinel_are_readable(configured):
    source, _, _ = configured(
        [
            {
                "localTablesVersion": 1,
                "parameterNumber": 250,
                "typeOfFirstFixedSurface": 166,
                "values": [-3.5, 9999.0, 0.0, 7.0],
            }
        ]
    )
    native = {
        "grib": {
            "localTablesVersion": 1,
            "parameterNumber": 250,
            "typeOfFirstFixedSurface": 166,
        }
    }
    with source:
        assert len(source.sel(native=native).all()) == 1
        field = source.sel(native=native).one()
        assert "level_type" not in field.identity.to_dict()
        array = field.to_xarray(rename="raw").raw
        np.testing.assert_array_equal(array.values.ravel(), [-3.5, 9999, 0, 7])


@pytest.fixture(params=[0, 6, 48])
def slhf_record(request):
    hour = request.param
    end = datetime(2026, 1, 1) + timedelta(hours=hour)
    return {
        "productDefinitionTemplateNumber": 8,
        "centre": 38,
        "subCentre": 0,
        "tablesVersion": 4,
        "localTablesVersion": 0,
        "productionStatusOfProcessedData": 0,
        "significanceOfReferenceTime": int(hour > 0),
        "typeOfProcessedData": int(hour > 0),
        "typeOfGeneratingProcess": 2 if hour else 0,
        "discipline": 0,
        "parameterCategory": 0,
        "parameterNumber": 10,
        "typeOfFirstFixedSurface": 1,
        "typeOfSecondFixedSurface": 255,
        "indicatorOfUnitOfTimeRange": 1,
        "forecastTime": 0,
        "typeOfStatisticalProcessing": 1,
        "numberOfTimeRange": 1,
        "typeOfTimeIncrement": 2,
        "indicatorOfUnitForTimeRange": 1,
        "lengthOfTimeRange": hour,
        "yearOfEndOfOverallTimeInterval": end.year,
        "monthOfEndOfOverallTimeInterval": end.month,
        "dayOfEndOfOverallTimeInterval": end.day,
        "hourOfEndOfOverallTimeInterval": end.hour,
        "minuteOfEndOfOverallTimeInterval": 0,
        "secondOfEndOfOverallTimeInterval": 0,
        "values": np.array([-120.0, 0.0, 80.0, 1000.0]) if hour else np.zeros(4),
    }


def test_slhf_accumulated_energy_preserves_native_values(write_grib, slhf_record):
    path = write_grib(records=[slhf_record])
    hour = slhf_record["lengthOfTimeRange"]
    with from_source(
        {"kind": "file", "path": str(path), "dataset": "cma_gfs_gmf"}
    ) as source:
        field = source.sel(
            parameter="cedarkit.slhf", time="2026-01-01T00:00:00Z", step=f"PT{hour}H"
        ).one()
        assert field.metadata["statistical_interval"] == {
            "start": "2026-01-01T00:00:00Z",
            "end": field.identity.valid_time,
        }
        assert field.metadata["source_unit"] == "J/m2"
        assert field.metadata["native_fields"]["units"] == "J m**-2"
        assert field.metadata["native_fields"]["parameterUnits"] == "W m-2"
        dataset = field.to_xarray()
        assert dataset.slhf.attrs["units"] == "J/m2"
        assert dataset.slhf.dims == ("time", "step", "latitude", "longitude")
        np.testing.assert_array_equal(
            dataset.slhf.values.reshape(-1), slhf_record["values"]
        )
        native = source.sel(
            native={"grib": {"parameterCategory": 0, "parameterNumber": 10}}
        ).one()
        np.testing.assert_array_equal(
            native.to_xarray(rename="raw").raw.values, dataset.slhf.values
        )


def test_slhf_unit_review_rejects_a_different_carrier(write_grib, slhf_record, tmp_path):
    path = write_grib(records=[{**slhf_record, "parameterNumber": 11}])
    source = {"kind": "file", "path": str(path), "dataset": "cma_gfs_gmf"}
    mappings = plan_source_binding(source).mappings[0].to_dict()
    for mapping in mappings["mappings"]:
        if mapping["parameter_id"] == "cedarkit.slhf":
            mapping["native"]["match"]["parameterNumber"] = 11
    resource = tmp_path / "slhf-mappings.json"
    resource.write_text(json.dumps(mappings))
    with from_source(
        source, context={"mappings": {"grib2": {"path": str(resource)}}}
    ) as owner:
        with pytest.raises(SourceError) as caught:
            owner.sel(parameter="cedarkit.slhf").one()
    assert caught.value.context["reason"] == "inconsistent_native_metadata"


@pytest.mark.parametrize(
    ("name", "category", "number", "surface", "decoder", "table"),
    [
        ("gusw", 4, 8, 1, "W m**-2", "8"),
        ("tusw", 4, 8, 8, "unknown", "8"),
        ("gulw", 5, 4, 1, "W m**-2", "W m-2"),
        ("tulw", 5, 4, 8, "unknown", "W m-2"),
    ],
)
def test_gfs_upward_energy_review_is_scoped(name, category, number, surface, decoder, table):
    pid = f"cedarkit.{name}"
    scope = {"dataset": "cma_gfs_gmf", "product": "orig", "product_version": "current"}
    native = {
        "edition": 2, "centre": 38, "subCentre": 0, "tablesVersion": 4,
        "localTablesVersion": 0, "productionStatusOfProcessedData": 0,
        "productDefinitionTemplateNumber": 8, "discipline": 0,
        "parameterCategory": category, "parameterNumber": number,
        "typeOfFirstFixedSurface": surface, "typeOfSecondFixedSurface": 255,
        "typeOfStatisticalProcessing": 1, "units": decoder, "parameterUnits": table,
    }
    assert _observed_units(native, scope, pid, "J/m2") == {"J/m2"}
    for changed in (
        {"typeOfFirstFixedSurface": 8 if surface == 1 else 1},
        {"typeOfStatisticalProcessing": 0},
        {"localTablesVersion": 1},
        {"parameterUnits": "kg/m2"},
    ):
        assert "J/m2" not in _observed_units(native | changed, scope, pid, "J/m2")
    for changed in ({"dataset": "cma_meso_1km"}, {"product_version": "previous"}):
        assert "J/m2" not in _observed_units(native, scope | changed, pid, "J/m2")


@pytest.fixture
def meso1_pwat_record():
    def make(hour=6, **overrides):
        return {
            "centre": 38,
            "subCentre": 0,
            "tablesVersion": 4,
            "localTablesVersion": 0,
            "productionStatusOfProcessedData": 0,
            "significanceOfReferenceTime": int(hour > 0),
            "typeOfProcessedData": int(hour > 0),
            "typeOfGeneratingProcess": 2 if hour else 0,
            "dataDate": 20261102,
            "dataTime": 1200,
            "productDefinitionTemplateNumber": 0,
            "discipline": 0,
            "parameterCategory": 1,
            "parameterNumber": 3,
            "typeOfFirstFixedSurface": 10,
            "typeOfSecondFixedSurface": 255,
            "indicatorOfUnitOfTimeRange": 0,
            "forecastTime": hour * 60,
            "values": np.array([0.0, 2.0, 15.0, 31.0]) if hour else np.zeros(4),
            **overrides,
        }
    return make


@pytest.mark.parametrize("hour", [0, 6, 48])
def test_meso1_pwat_preserves_mass_per_area_and_entire_atmosphere(
    write_grib, meso1_pwat_record, hour
):
    record = meso1_pwat_record(hour)
    path = write_grib(records=[record])
    with from_source({"kind": "file", "path": str(path), "dataset": "cma_meso_1km"}) as source:
        field = source.sel(parameter="cedarkit.pwat", time="2026-11-02T12:00:00Z", step=f"PT{hour}H").one()
        assert field.identity.level_type == "entire_atmosphere"
        assert field.metadata["source_unit"] == "kg/m2"
        assert field.metadata["mapping_ids"] == (f"pwat.instantaneous.{'forecast' if hour else 'initial'}",)
        dataset = field.to_xarray()
        assert dataset.pwat.attrs["units"] == "kg/m2"
        assert dataset.pwat.dims == ("time", "step", "latitude", "longitude")
        assert "entire_atmosphere" not in dataset.coords
        assert field.report.overall["status"] == "unchecked"
        assert any(reason["code"] == "expected_set_unknown" for reason in field.report.overall["reasons"])
        np.testing.assert_array_equal(dataset.pwat.values.ravel(), record["values"])


@pytest.mark.parametrize("query", [
    {"time": "2026-11-02T12:00:00Z", "step": "PT12H"},
    {"time": "2026-11-03T12:00:00Z", "step": "PT6H"},
])
def test_meso1_pwat_uses_encoded_time_for_other_orig_files(write_grib, meso1_pwat_record, query):
    path = write_grib(records=[meso1_pwat_record()])
    with from_source({"kind": "file", "path": str(path), "dataset": "cma_meso_1km"}) as source:
        fields = source.sel(parameter="cedarkit.pwat", **query).all()
        assert not fields
        assert fields.report.overall["status"] == "unchecked"


def test_meso1_pwat_rejects_surface_refinement(write_grib, meso1_pwat_record):
    from cedarkit_query import QueryError

    path = write_grib(records=[meso1_pwat_record()])
    with from_source({"kind": "file", "path": str(path), "dataset": "cma_meso_1km"}) as source:
        with pytest.raises(QueryError) as caught:
            source.sel(parameter="cedarkit.pwat", level_type="surface").one()
    assert caught.value.code == "constraint_conflict"


def test_meso1_pwat_rejects_humidity_units_on_a_misbound_carrier(
    write_grib, meso1_pwat_record, tmp_path
):
    path = write_grib(records=[meso1_pwat_record(parameterNumber=0)])
    source = {"kind": "file", "path": str(path), "dataset": "cma_meso_1km"}
    resource = plan_source_binding(source).mappings[0].to_dict()
    for mapping in resource["mappings"]:
        if mapping["parameter_id"] == "cedarkit.pwat":
            mapping["native"]["match"]["parameterNumber"] = 0
    config = tmp_path / "misbound-pwat.json"
    config.write_text(json.dumps(resource))
    with from_source(source, context={"mappings": {"grib2": {"path": str(config)}}}) as owner:
        with pytest.raises(SourceError) as caught:
            owner.sel(parameter="cedarkit.pwat", time="2026-11-02T12:00:00Z", step="PT6H").one()
    assert caught.value.context["reason"] == "inconsistent_native_metadata"


def test_meso1_pwat_keeps_bitmap_missing_values_and_source_ownership(
    write_grib, meso1_pwat_record
):
    path = write_grib(records=[meso1_pwat_record(bitmapPresent=1, missingValue=9999, values=[1, 9999, 3, 0])])
    with from_source({"kind": "file", "path": str(path), "dataset": "cma_meso_1km"}) as source:
        field = source.sel(parameter="cedarkit.pwat", time="2026-11-02T12:00:00Z", step="PT6H").one()
        array = field.to_xarray().pwat
        np.testing.assert_array_equal(np.isnan(array.values.ravel()), [False, True, False, False])
        np.testing.assert_array_equal(array.values.ravel()[[0, 2, 3]], [1, 3, 0])
    assert np.isnan(array.values.ravel()[1])
    with pytest.raises(SourceError):
        field.to_xarray()


def test_meso1_pwat_required_does_not_invent_an_expected_domain(
    write_grib, meso1_pwat_record
):
    from cedarkit_query import CompletenessError

    path = write_grib(records=[meso1_pwat_record()])
    with from_source({"kind": "file", "path": str(path), "dataset": "cma_meso_1km"}) as source:
        with pytest.raises(CompletenessError):
            source.sel(parameter="cedarkit.pwat", time="2026-11-02T12:00:00Z", step="PT6H").one(completeness="required")


def test_lossless_grib_preserves_value_quantization_evidence(write_grib, meso1_pwat_record):
    path = write_grib(records=[meso1_pwat_record()])
    with from_source({"kind": "file", "path": str(path), "dataset": "cma_meso_1km"}) as source:
        field = source.sel(parameter="cedarkit.pwat", time="2026-11-02T12:00:00Z", step="PT6H").one()
        encoding = field.metadata["value_encoding"]
        assert encoding["unit"] == "kg/m2"
        assert encoding["quantization_error"] == pytest.approx(0.5 * 2**encoding["binary_scale_factor"] * 10**(-encoding["decimal_scale_factor"]))
        assert "binaryScaleFactor" not in field.identity.to_dict().get("native", {}).get("grib", {})
