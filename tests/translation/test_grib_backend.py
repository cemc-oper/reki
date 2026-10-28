"""Actual ecCodes I/O on disposable generated GRIB2; never business acceptance."""

import json
from dataclasses import replace
import numpy as np
import pytest
import eccodes

from cedarkit_query import Query, QueryError, SourceError, CompletenessError
from reki.catalog import plan_source_binding
from reki.selection.core import construct_source
from reki.translation.grib_backend import GribBackend


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
def configured(tmp_path, write_grib):
    def make(records=None, *, business=True, expected_domain=None):
        file = write_grib(records=records)
        context = {}
        if business:
            parameters = {
                "api_version": "cedarkit.parameters/v1",
                "id": "SYNTHETIC.params",
                "version": "1",
                "parameters": [
                    {"parameter_id": "synthetic.t", "name": "t", "unit": "K"}
                ],
            }
            mappings = {
                "api_version": "cedarkit.mappings/v1",
                "id": "SYNTHETIC.maps",
                "version": "1",
                "backend": "grib2",
                "tables": [],
                "mappings": [
                    {
                        "id": "SYNTHETIC.t",
                        "parameter_id": "synthetic.t",
                        "backend": "grib2",
                        "applies_to": {},
                        "when": {},
                        "native": {
                            "match": {
                                "discipline": 0,
                                "parameterCategory": 0,
                                "parameterNumber": 0,
                            },
                            "translate": {
                                "vertical": {"rule": "grib.fixed_surfaces"},
                                "time": {"rule": "grib.time"},
                                "unit": {"rule": "common.value_unit"},
                            },
                        },
                        "evidence": [
                            "SYNTHETIC generated GRIB; not a business product mapping"
                        ],
                    }
                ],
            }
            for name, value in (("parameters", parameters), ("mappings", mappings)):
                (tmp_path / (name + ".json")).write_text(json.dumps(value))
            context = {
                "parameter_registry": {"path": str(tmp_path / "parameters.json")},
                "mappings": {"grib2": {"path": str(tmp_path / "mappings.json")}},
            }
        config = plan_source_binding(
            {"kind": "file", "path": str(file)}, context=context
        )
        backend = GribBackend(
            config,
            expected_domain=expected_domain,
            identity_fields=("parameter", "level_type", "level", "time", "step"),
        )
        return construct_source(config, backend), file, context

    return make


def test_metadata_selection_is_lazy_and_values_coordinates_are_independent(
    configured, monkeypatch
):
    source, file, _ = configured()
    selected = source.sel(
        parameter="t", level_type="pressure", level=85000, level_unit="Pa"
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
    ds = result.to_xarray()
    np.testing.assert_array_equal(
        ds.t.values.reshape(2, 2), [[280.0, 281.0], [282.0, 283.0]]
    )
    assert ds.t.dims == ("time", "step", "pressure", "latitude", "longitude")
    assert ds.pressure.values[0] == 850 and ds.t.attrs["units"] == "K"
    assert len(loads) == 1
    source.close()
    assert ds.t.values.flat[0] == 280.0
    with pytest.raises(SourceError):
        result.to_xarray()


def test_equivalent_encodings_all_enter_candidates_and_distinct_records_conflict(
    configured,
):
    source, _, _ = configured(
        [
            {},
            {
                "scaleFactorOfFirstFixedSurface": 1,
                "scaledValueOfFirstFixedSurface": 850000,
            },
        ]
    )
    selected = source.sel(parameter="t", level_type="pressure", level=850)
    fields = selected.all()
    assert len(fields) == 2 and all(f.identity.level == 850 for f in fields)
    with pytest.raises(QueryError) as exc:
        selected.one()
    assert exc.value.code == "multiple_matches"
    with pytest.raises(QueryError) as exc:
        fields.to_xarray()
    assert exc.value.code == "duplicate_field"


def test_source_order_and_exact_record_dedup_across_duplicate_paths(
    configured, write_grib
):
    source, file, _ = configured([{}, {"scaledValueOfFirstFixedSurface": 50000}])
    config = replace(
        source.configuration, source={"kind": "file", "path": (str(file), str(file))}
    )
    source = construct_source(config, GribBackend(config))
    fields = source.sel(parameter="t").all()
    assert len(fields) == 2 and fields.first().identity.level == 850
    assert source.sel(parameter="t").first().identity.level == 850


def test_file_replacement_fails_delayed_reference(configured, write_grib):
    source, file, _ = configured()
    field = source.sel(parameter="t").one()
    replacement = write_grib("replacement.grib2")
    replacement.replace(file)
    with pytest.raises(SourceError) as exc:
        field.to_xarray()
    assert exc.value.context["reason"] == "resource_changed"


def test_independent_expected_domain_is_not_observed_messages(configured):
    domain = [
        Query(
            parameter="synthetic.t",
            level_type="pressure",
            level=850,
            time="2026-01-01T00:00:00Z",
            step="PT6H",
        ),
        Query(
            parameter="synthetic.t",
            level_type="pressure",
            level=500,
            time="2026-01-01T00:00:00Z",
            step="PT6H",
        ),
    ]
    source, _, _ = configured(expected_domain=domain)
    selected = source.sel(parameter="t")
    with pytest.raises(CompletenessError) as exc:
        selected.all(completeness="required")
    assert exc.value.report.overall["expected_count"] == 2
    assert exc.value.report.overall["missing"][0]["selection"]["level"] == 500


def test_native_query_does_not_fabricate_business_id(configured):
    source, _, _ = configured(business=False)
    field = source.sel(native={"grib": {"parameterNumber": 0}}).one()
    assert "parameter" not in field.identity.to_dict()
    ds = field.to_xarray(rename="native_temperature")
    assert "cedarkit_parameter_id" not in ds.native_temperature.attrs
    assert ds.native_temperature.attrs["units"] == "K"


def test_known_unsupported_key_edition_and_template_fail_before_scan(
    configured, monkeypatch
):
    source, _, _ = configured(business=False)

    def forbidden(*args, **kwargs):
        raise AssertionError("selection must not scan")

    monkeypatch.setattr(eccodes, "codes_grib_new_from_file", forbidden)
    for selector in (
        {"unregisteredKey": 1},
        {"edition": 1},
        {"productDefinitionTemplateNumber": 40},
    ):
        with pytest.raises(QueryError) as exc:
            source.sel(native={"grib": selector})
        assert exc.value.code == "unsupported"


def test_no_match_is_empty_but_truncated_stream_is_a_source_error(configured):
    source, file, _ = configured()
    assert len(source.sel(parameter="t", level_type="pressure", level=700).all()) == 0
    payload = file.read_bytes()
    file.write_bytes(payload[:-16])
    with pytest.raises(SourceError) as exc:
        source.sel(parameter="t").all()
    assert exc.value.code == "decode_failed" and "report" not in exc.value.to_dict()


def test_fresh_public_file_pipeline_has_no_cfgrib_or_legacy_package_import(configured):
    import subprocess, sys

    _, file, context = configured()
    script = """import json,sys
from reki import from_source
with from_source({"kind":"file","path":sys.argv[1]},context=json.loads(sys.argv[2])) as source:
    ds=source.sel(parameter="t").one().to_xarray()
    assert ds.t.values.flat[0]==280.
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
    fields = construct_source(config, GribBackend(config)).sel(parameter="t").all()
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
    fields = source.sel(parameter="t").all()
    assert len(fields) == 1 and fields.report.overall["field_count"] == 1
    assert fields.to_xarray().t.isnull().all()


def test_internal_definition_inputs_are_frozen(configured):
    domain = [
        Query(
            parameter="synthetic.t",
            level_type="pressure",
            level=850,
            time="2026-01-01T00:00:00Z",
            step="PT6H",
        )
    ]
    source, _, _ = configured(expected_domain=domain)
    domain.clear()
    assert source.sel(parameter="t").explain().analysis["expected_count"] == 1


@pytest.mark.parametrize(
    "settings,reason",
    [
        ({"parameterNumber": 224}, "inconsistent_native_metadata"),
        (
            {"parameterNumber": 224, "localTablesVersion": 1},
            "unsupported_native_encoding",
        ),
        ({"parameterNumber": 255}, "missing_native_metadata"),
        ({"Ni": 3}, "inconsistent_native_metadata"),
        ({"Ni": 0}, "inconsistent_native_metadata"),
        ({"jPointsAreConsecutive": 1}, "unsupported_native_encoding"),
        ({"alternativeRowScanning": 1}, "unsupported_native_encoding"),
    ],
)
def test_raw_profile_and_grid_boundaries_remain_structured(
    configured, settings, reason
):
    source, _, _ = configured([settings], business=False)
    with source, pytest.raises(SourceError) as exc:
        source.sel(native={"grib": {"discipline": 0}}).all()
    assert exc.value.code == "metadata_interpretation_failed"
    assert exc.value.context["reason"] == reason


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
        field = source.sel(parameter="t").one()
        raw = field.metadata["native_fields"]
        assert raw["Ni"] == raw["Nj"] == 2
        assert raw["numberOfDataPoints"] == 4
        assert raw["gridDefinitionTemplateNumber"] == 0
        assert raw["scanningMode"] >= 0
        ds = field.to_xarray()
        np.testing.assert_array_equal(ds.latitude, lat)
        np.testing.assert_array_equal(ds.longitude, lon)
        np.testing.assert_array_equal(
            ds.t.values.reshape(2, 2), [[280, 281], [282, 283]]
        )
