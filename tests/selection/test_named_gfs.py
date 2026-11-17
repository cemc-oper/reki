"""Frozen GFS queries against small, independently written GRIB2 records."""

import json

import eccodes
import numpy as np
import pytest
import xarray as xr
import yaml
from cedarkit_query import (
    CompletenessError,
    QueryError,
    QueryReport,
    Request,
    SourceError,
)
from reki import from_source
from reki.diagnostics import collect_io_metrics

TIME = {"time": "2026-11-02T12:00:00Z", "step": "PT6H"}
T2M = {"parameter": "cedarkit.t2m", **TIME}
T850 = {
    "parameter": "cedarkit.t",
    "level_type": "pressure",
    "level": 850,
    "level_unit": "hPa",
    **TIME,
}
RELATIVE_FILE = (
    "DATA/NAFP/NMC/GRAPES-GFS-GLB/2026/20261102/"
    "Z_NAFP_C_BABJ_20261102120000_P_NWPC-GRAPES-GFS-GLB-00600.grib2"
)


def write_fields(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    offsets = []
    with path.open("wb") as stream:
        for level_type, level, value in records:
            handle = eccodes.codes_grib_new_from_samples("regular_ll_sfc_grib2")
            try:
                for key, val in {
                    "centre": 38,
                    "subCentre": 0,
                    "tablesVersion": 4,
                    "localTablesVersion": 0,
                    "productionStatusOfProcessedData": 0,
                    "discipline": 0,
                    "parameterCategory": 0,
                    "parameterNumber": 0,
                    "typeOfLevel": level_type,
                    "level": level,
                    "dataDate": 20261102,
                    "dataTime": 1200,
                    "significanceOfReferenceTime": 1,
                    "forecastTime": 6,
                }.items():
                    eccodes.codes_set(handle, key, val)
                eccodes.codes_set_values(
                    handle,
                    np.full(
                        eccodes.codes_get_long(handle, "numberOfDataPoints"), value
                    ),
                )
                offsets.append(stream.tell())
                eccodes.codes_write(handle, stream)
            finally:
                eccodes.codes_release(handle)
    return offsets


@pytest.fixture
def dataset(tmp_path):
    path = tmp_path / RELATIVE_FILE
    offsets = write_fields(
        path,
        [
            ("heightAboveGround", 10, 270),  # Same coarse native keys as t2m
            ("heightAboveGround", 2, 282),
            ("isobaricInhPa", 500, 252),  # Same coarse native keys as t850
            ("isobaricInhPa", 850, 273),
        ],
    )
    return {"kind": "local", "dataset": "CMA-GFS", "root": str(tmp_path)}, path, offsets


@pytest.mark.parametrize(
    "query,name,axis,level,value,record",
    [
        (T2M, "t2m", "height_above_ground", 2, 282, 1),
        (T850, "t", "pressure", 850, 273, 3),
    ],
)
def test_python_and_requests_read_named_temperature(
    dataset, tmp_path, query, name, axis, level, value, record
):
    source, path, offsets = dataset
    with collect_io_metrics() as metrics:
        with from_source(source) as owner:
            selection = owner.sel(**query)
            analysis = selection.explain().to_dict()["analysis"]
            assert analysis["expected_count"] == 1
            branch = analysis["translations"][0]["branches"][0]
            assert branch["basis"][0]["mapping"] == f"{name}.operational.instantaneous"
            assert branch["residual"]["level"] == level
            for metric in (
                "file_open_count",
                "grib_header_scan_count",
                "value_decode_count",
            ):
                assert metrics.snapshot()[metric] == 0
            field = selection.one(completeness="required")
            assert field.metadata["source"]["offset"] == offsets[record]
            assert field.metadata["source"]["path"] == str(path)
            assert field.metadata["source_unit"] == "K"
            assert field.report.overall["status"] == "complete"
            assert field.report.overall["field_count"] == 1
            assert metrics.snapshot()["value_decode_count"] == 0
            actual = field.to_xarray()
            assert actual[name].dims == ("time", "step", axis, "latitude", "longitude")
            assert actual[axis].item() == level
            assert actual[name].attrs["cedarkit_parameter_id"] == query["parameter"]
            assert actual[name].attrs["units"] == "K"
            assert actual.valid_time.values[0, 0] == np.datetime64("2026-11-02T18:00")
            assert (
                QueryReport.from_json(actual.attrs["cedarkit_query_report"])
                == field.report
            )
            assert field.report.context["source"]["product_version"] == "current"
            renamed = field.to_xarray(rename="temperature")
            assert renamed.temperature.attrs == actual[name].attrs
            assert renamed.attrs == actual.attrs
        np.testing.assert_array_equal(actual[name], value)
        with pytest.raises(SourceError) as closed:
            field.to_xarray()
        assert closed.value.code == "io_error"

    data = {
        "api_version": "cedarkit.request/v1",
        "source": {**source, "root": "."},
        "queries": [query],
        "completeness": "required",
    }
    for suffix, encode in (("json", json.dumps), ("yaml", yaml.safe_dump)):
        request_path = tmp_path / f"query.{suffix}"
        request_path.write_text(encode(data))
        request = Request.load(request_path)
        with from_source(request.source, context=request.context) as owner:
            result = owner.sel(request.queries).one(completeness=request.completeness)
            request_ds = result.to_xarray()
            assert (
                QueryReport.from_json(request_ds.attrs["cedarkit_query_report"])
                == field.report
            )
            # The input formats may order object keys differently.
            for ds in (request_ds, actual):
                ds.attrs["cedarkit_query_report"] = field.report.to_json()
                ds[name].attrs["cedarkit_query_report"] = field.report.to_json()
            xr.testing.assert_identical(request_ds, actual)


def test_named_and_native_union_deduplicates_and_keeps_paired_conditions(dataset):
    source, path, _ = dataset
    with from_source(
        {"kind": "file", "path": str(path), "dataset": source["dataset"]}
    ) as owner:
        fields = owner.sel([T2M, T850, {"native": {"grib": {"shortName": "2t"}}}]).all()
        assert len(fields) == 2
        assert [field.identity.parameter for field in fields] == [
            "cedarkit.t2m",
            "cedarkit.t",
        ]
        assert set(fields.to_xarray().data_vars) == {"t2m", "t"}
        assert (
            owner.sel(T850).sel(level_unit="Pa", level=85000).one().identity.level
            == 850
        )
        assert owner.sel(T850).sel(level=500).all().report.overall["field_count"] == 0
        t500 = owner.sel(
            {**T850, "level": 500, "native": {"grib": {"parameterNumber": 0}}}
        ).one()
        assert t500.identity.level == 500
        assert t500.report.overall["status"] == "unchecked"


def test_plain_file_uses_the_generic_named_mapping_and_an_unknown_expected_set(dataset):
    _, path, offsets = dataset
    with from_source({"kind": "file", "path": str(path)}) as owner:
        for name in ("t2m", "cedarkit.t2m", "2t"):
            selection = owner.sel({**T2M, "parameter": name})
            explanation = selection.explain().to_dict()
            assert explanation["context"]["source"] == {"kind": "file"}
            assert explanation["analysis"]["expected_count"] is None
            branch = explanation["analysis"]["translations"][0]["branches"][0]
            assert branch["scope"] == {}
            assert [
                row["resource"]["id"] for row in branch["basis"] if "resource" in row
            ] == ["cedarkit.grib2.generic", "cedarkit.parameters.public"]
            assert branch["basis"][0]["mapping"] == "wmo.t2m.instantaneous.103"
            field = selection.one()
            assert field.metadata["source"]["offset"] == offsets[1]
            assert field.identity.parameter == "cedarkit.t2m"
            assert field.identity.level == 2
            assert field.report.to_dict()["context"]["definitions"] == (
                explanation["context"]["definitions"]
            )
            assert field.report.overall["status"] == "unchecked"
            assert [row["code"] for row in field.report.overall["reasons"]] == [
                "expected_set_unknown"
            ]
            actual = field.to_xarray().t2m
            assert actual.attrs["units"] == "K"
            np.testing.assert_array_equal(actual, 282)

        with pytest.raises(CompletenessError) as caught:
            selection.one(completeness="required")
        assert caught.value.code == "completeness_undetermined"
        with pytest.raises(QueryError) as caught:
            owner.sel(parameter="kidx")
        assert caught.value.code == "unsupported"
        assert caught.value.context["reason"] == "mapping_coverage_gap"
        native = owner.sel(native={"grib": {"shortName": "2t"}}).one()
        assert "parameter" not in native.identity.to_dict()


def test_missing_and_unbounded_expectations_are_distinct(tmp_path):
    path = tmp_path / RELATIVE_FILE
    write_fields(path, [("heightAboveGround", 2, 282)])
    source = {"kind": "local", "dataset": "cma_gfs_gmf", "root": str(tmp_path)}
    with from_source(source) as owner:
        selection = owner.sel([T2M, T850])
        fields = selection.all()
        report = fields.report
        assert set(fields.to_xarray(rename={"t": "missing", "t2m": "temperature"})) == {
            "temperature"
        }
        assert report.overall["status"] == "missing"
        assert report.overall["missing"][0]["selection"]["parameter"] == "cedarkit.t"
        with pytest.raises(CompletenessError) as missing:
            selection.one(completeness="required")
        assert missing.value.code == "missing_fields"
        with pytest.raises(QueryError) as empty:
            owner.sel(T850).one()
        assert empty.value.code == "no_match"
        unknown = owner.sel(parameter="t2m", time=TIME["time"])
        assert unknown.all().report.overall["status"] == "unchecked"
        with pytest.raises(CompletenessError) as unchecked:
            unknown.all(completeness="required")
        assert unchecked.value.code == "completeness_undetermined"


@pytest.mark.parametrize(
    "changes,code,reason",
    [
        ({"level": 10}, "constraint_conflict", "fixed_condition_conflict"),
        ({"member": 0}, "constraint_conflict", "fixed_condition_conflict"),
        (
            {"native": {"grib": {"parameterNumber": [0, 3]}}},
            "constraint_conflict",
            "fixed_condition_conflict",
        ),
        (
            {"native": {"grib": {"parameterNumber": 3}}},
            "constraint_conflict",
            "fixed_condition_conflict",
        ),
    ],
)
def test_named_static_errors_do_not_discover_files(dataset, changes, code, reason):
    source, _, _ = dataset
    with from_source(source) as owner, pytest.raises(QueryError) as caught:
        owner.sel({**T2M, **changes})
    assert caught.value.code == code
    assert caught.value.context["reason"] == reason


def test_named_temperature_uses_encoded_fixed_surface(dataset):
    source, _, _ = dataset
    with from_source(source) as owner:
        fields = owner.sel(parameter="t", level_type="height_above_sea", **TIME).all()
        assert not fields
        assert fields.report.overall["status"] == "unchecked"


def test_named_unit_conversion_keeps_native_provenance(dataset, tmp_path):
    source, _, _ = dataset
    with from_source(source) as owner:
        from reki.catalog import load_resource

        catalog = load_resource(owner.configuration.definitions[0]["reference"], "catalog")
        registry = load_resource(
            owner.configuration.definitions[1]["reference"], "parameters", base_dir=catalog.base_dir
        ).value.to_dict()
    next(row for row in registry["parameters"] if row["parameter_id"] == "cedarkit.t")[
        "unit"
    ] = "degC"
    registry_path = tmp_path / "temperature-parameters.json"
    registry_path.write_text(json.dumps(registry))
    with from_source(
        source, context={"parameter_registry": {"path": str(registry_path)}}
    ) as owner:
        field = owner.sel(T2M).one()
        assert field.metadata["native_fields"]["units"] == "K"
        assert field.metadata["source_unit"] == "K"
        assert field.metadata["unit"] == "degC"
        result = field.to_xarray()
        assert result.t2m.attrs["units"] == "degC"
        np.testing.assert_allclose(result.t2m, 282 - 273.15)


def test_target_metadata_failure_and_bad_stream_are_source_errors(dataset):
    source, path, offsets = dataset
    with path.open("rb") as stream:
        stream.seek(offsets[1])
        handle = eccodes.codes_grib_new_from_file(stream)
        try:
            eccodes.codes_set_missing(handle, "scaledValueOfFirstFixedSurface")
            damaged = eccodes.codes_get_message(handle)
        finally:
            eccodes.codes_release(handle)
    path.write_bytes(damaged)
    with from_source(source) as owner, pytest.raises(SourceError) as caught:
        owner.sel(T2M).one()
    assert caught.value.code == "metadata_interpretation_failed"
    assert caught.value.context["reason"] == "missing_native_metadata"
    assert caught.value.context["offset"] == 0
    assert caught.value.context["resource"] == str(path)
    path.write_bytes(b"invalid GRIB")
    with from_source(source) as owner, pytest.raises(SourceError) as caught:
        owner.sel(T2M).one()
    assert caught.value.code == "decode_failed"


def test_overlapping_mapping_is_ambiguous_before_scan(dataset, tmp_path):
    source, _, _ = dataset
    with from_source(source) as owner:
        resource = owner.configuration.mappings[0].to_dict()
    base_mapping = next(
        row
        for row in resource["mappings"]
        if row["id"] == "t.operational.instantaneous"
    )
    alternate = json.loads(json.dumps(base_mapping))
    alternate["id"] = "overlapping-temperature"
    alternate["native"]["match"].pop("tablesVersion")
    resource["mappings"].append(alternate)
    path = tmp_path / "overlapping-mappings.json"
    path.write_text(json.dumps(resource))
    context = {"mappings": {"grib2": {"path": str(path)}}}
    with collect_io_metrics() as metrics, from_source(source, context=context) as owner:
        with pytest.raises(QueryError) as caught:
            owner.sel(T850)
        assert caught.value.code == "invalid_config"
        assert caught.value.context["reason"] == "ambiguous_mapping"
        assert metrics.snapshot()["grib_header_scan_count"] == 0
