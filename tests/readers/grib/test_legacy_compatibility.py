"""Q15/Q16 protected functions using real small GRIB/NetCDF/GrADS files."""

from pathlib import Path
import importlib
import warnings

import eccodes as ec
import numpy as np
import pytest
import xarray as xr
from xarray.core.indexing import LazilyIndexedArray

from cedarkit_query import QueryError, SourceError, QueryReport
from reki.diagnostics import collect_io_metrics
from reki.format.grib import load_field_from_file as ordinary
from reki.readers.grib.eccodes import (
    load_field_from_file as single,
    load_field_from_files,
)
from reki.readers.grib import load_fields_from_file


def _write_fields(path, records):
    with path.open("wb") as f:
        for i, (name, level, step) in enumerate(records):
            m = ec.codes_grib_new_from_samples("regular_ll_pl_grib2")
            try:
                for k, v in {
                    "Ni": 4,
                    "Nj": 3,
                    "latitudeOfFirstGridPointInDegrees": 32.0,
                    "latitudeOfLastGridPointInDegrees": 30.0,
                    "longitudeOfFirstGridPointInDegrees": 100.0,
                    "longitudeOfLastGridPointInDegrees": 103.0,
                    "iDirectionIncrementInDegrees": 1.0,
                    "jDirectionIncrementInDegrees": 1.0,
                    "shortName": name,
                    "level": level,
                    "dataDate": 20261102,
                    "dataTime": 1200,
                    "step": step,
                    "bitmapPresent": 1,
                    "missingValue": 9999,
                }.items():
                    ec.codes_set(m, k, v)
                a = np.arange(12, dtype=float) + i * 20
                a[5] = 9999
                ec.codes_set_values(m, a)
                f.write(ec.codes_get_message(m))
            finally:
                ec.codes_release(m)
    return path


@pytest.fixture
def raw(tmp_path):
    return _write_fields(
        tmp_path / "fields.grib2",
        [("t", 850, 6), ("u", 850, 6), ("t", 500, 6), ("t", 1000, 6), ("t", 850, 12)],
    )


def decoded(path):
    rows = []
    with Path(path).open("rb") as f:
        while (m := ec.codes_grib_new_from_file(f)) is not None:
            try:
                values = ec.codes_get_array(m, "values").reshape(3, 4)
                values[ec.codes_get_array(m, "bitmap").reshape(3, 4) == 0] = np.nan
                rows.append((ec.codes_get_message(m), values))
            finally:
                ec.codes_release(m)
    return rows


@pytest.mark.parametrize(
    ("fn", "level_coord", "level_dtype"),
    [(ordinary, "isobaricInhPa", np.int64), (single, "pl", np.float64)],
)
def test_high_frequency_first_order_partial_levels_names_and_units(raw, fn, level_coord, level_dtype):
    truth = decoded(raw)
    first = fn(raw, parameter=None)
    np.testing.assert_equal(first.values, truth[0][1])
    assert first.attrs["units"] == "K"
    by_keys = fn(
        raw,
        parameter={"shortName": "t"},
        level_type={"typeOfFirstFixedSurface:int": 100},
        level={"level": 850},
    )
    np.testing.assert_equal(by_keys.values, truth[0][1])
    single_level = fn(raw, parameter="t", level_type="pl", level=[500])
    assert single_level[level_coord].ndim == 0
    assert single_level[level_coord].item() == 500
    assert single_level[level_coord].dtype == level_dtype
    assert (
        fn(raw, parameter="absent") is None and fn(raw, parameter="t", level=[]) is None
    )
    data = fn(
        raw,
        parameter="t",
        level_type="pl",
        level=[500, 850, 700],
        field_name="temperature",
    )
    assert data.name == "temperature" and data[level_coord].values.tolist() == [850, 500, 850]
    np.testing.assert_equal(data.values, np.stack([truth[i][1] for i in [0, 2, 4]]))
    assert "cedarkit_query_report" not in data.attrs
    pa = fn(raw, parameter="t", level_type="pl", level=850, level_dim="isobaricInPa")
    assert pa.isobaricInPa.item() == 85000


@pytest.mark.parametrize(("fn", "level_coord"), [(ordinary, "isobaricInhPa"), (single, "pl")])
def test_lazy_first_access_does_not_decode_excluded_messages(raw, fn, level_coord):
    with collect_io_metrics() as metrics:
        value = fn(raw, parameter="t", level_type="pl", level="all", lazy=True)
        assert isinstance(value.variable._data, LazilyIndexedArray)
        assert metrics.snapshot()["value_decode_count"] == 0
        np.testing.assert_equal(value.isel({level_coord: 1}).values, decoded(raw)[2][1])
        assert metrics.snapshot()["value_decode_count"] == 1


@pytest.mark.parametrize("fn", [ordinary, single])
@pytest.mark.parametrize(
    ("short_name", "level", "cemc", "wgrib2", "description", "unit"),
    [("2t", 2, "t2m", "TMP", "2 metre temperature", "K"),
     ("d", 850, "div", "RELD", "Divergence", "s**-1")],
)
def test_legacy_grib_style_metadata(tmp_path, fn, short_name, level, cemc, wgrib2, description, unit):
    path = _write_fields(tmp_path / "style.grib2", [(short_name, level, 6)])
    named = fn(path, parameter=short_name)
    by_keys = fn(path, parameter={"shortName": short_name})
    assert named.name == short_name
    assert by_keys.name == cemc
    expected = {
        "cemc_name": cemc, "eccodes_name": short_name, "wgrib2_name": wgrib2,
        "long_name": description, "units": unit, "GRIB_units": unit,
    }
    for actual in (named, by_keys):
        assert {name: actual.attrs[name] for name in expected} == expected
        np.testing.assert_equal(actual.values, decoded(path)[0][1])


@pytest.mark.parametrize("fn", [ordinary, single, load_fields_from_file])
@pytest.mark.parametrize(
    "with_index", [False, True, "/missing/not-writable/legacy.idx"]
)
def test_index_warning_once_at_caller_without_touching_index(
    raw, fn, with_index, monkeypatch
):
    import reki.readers.grib.index.store as store

    monkeypatch.setattr(
        store.IndexStore,
        "__init__",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("index access")),
    )
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        fn(raw, parameter="t", level_type="pl", level="all", with_index=with_index)
    relevant = [
        w
        for w in captured
        if issubclass(w.category, FutureWarning)
        and "indexes have been retired" in str(w.message)
    ]
    assert len(relevant) == (0 if with_index is False else 1)
    if relevant:
        assert Path(relevant[0].filename) == Path(__file__)
    assert not list(raw.parent.glob("*.idx"))


@pytest.mark.parametrize("report_options", [{}, {"include_report": True}])
def test_low_frequency_organization_report_zero_and_unsupported(raw, report_options):
    include_report = report_options.get("include_report", False)
    key = "cedarkit_query_report"
    dataset = load_fields_from_file(
        raw, parameter="t", level_type="pl", level="all", **report_options
    )
    assert set(dataset.dims) == {"time", "step", "pressure", "latitude", "longitude"}
    assert dataset.sizes["pressure"] == 3 and dataset.sizes["step"] == 2
    (variable,) = dataset.data_vars.values()
    assert variable.attrs["units"] == "K"
    assert (key in dataset.attrs) == (key in variable.attrs) == include_report
    if include_report:
        snapshot = dataset.attrs[key]
        assert variable.attrs[key] == snapshot
        report = QueryReport.from_json(snapshot)
        assert report.overall["status"] == "unchecked"
        assert "selection=" in report.context["origins"]["adapter"]
    array = load_field_from_files(
        [raw, raw],
        parameter="t",
        level_type="pl",
        level=[850, 500, 700],
        field_name="chosen",
        **report_options,
    )
    assert array.name == "chosen" and array.sizes["pressure"] == 2
    assert (key in array.attrs) == include_report
    if include_report:
        assert QueryReport.from_json(array.attrs[key]).overall["field_count"] == 3
    assert (
        load_field_from_files([raw], parameter="absent", level_type=None, level=None)
        is None
    )
    empty = load_fields_from_file(raw, parameter="absent", **report_options)
    assert not empty.data_vars and (key in empty.attrs) == include_report
    for kwargs in [{"lazy": True}, {"level_dim": "pl"}]:
        with pytest.raises(QueryError, match="unsupported"):
            load_field_from_files([raw], "t", "pl", None, **kwargs)
    with pytest.raises(QueryError, match="invalid_query"):
        load_field_from_files([], "t", "pl", None)


def test_collection_error_precedence_and_source_fault(raw, tmp_path):
    duplicate = tmp_path / "copy.grib2"
    duplicate.write_bytes(raw.read_bytes())
    with pytest.raises(QueryError, match="multiple_variables"):
        load_field_from_files([raw, duplicate], None, None, "all")
    with pytest.raises(QueryError, match="duplicate_field"):
        load_field_from_files([raw, duplicate], "t", "pl", None)
    with pytest.raises(SourceError, match="resource_not_found"):
        load_field_from_files([raw, tmp_path / "missing"], "t", "pl", None)


def test_collection_level_none_selects_physical_first_per_file(tmp_path):
    early = _write_fields(tmp_path / "early.grib2", [("u", 850, 6), ("t", 850, 6), ("t", 500, 6)])
    late = _write_fields(tmp_path / "late.grib2", [("t", 500, 12), ("t", 850, 12)])
    truth = [decoded(early)[1][1], decoded(late)[0][1]]
    dims = ("time", "step", "latitude", "longitude")
    for path, pressure, expected in zip((early, late), (850.0, 500.0), truth):
        field = load_field_from_files([path], "t", "pl", None)
        assert field.dims == dims and field.shape == (1, 1, 3, 4)
        assert field.name == "t" and field.pl.ndim == 0 and field.pl.item() == pressure
        np.testing.assert_equal(field.isel(time=0, step=0).values, expected)

    with collect_io_metrics() as metrics:
        combined = load_field_from_files([late, early], "t", "pl", None, include_report=True)
        assert metrics.snapshot()["grib_header_scan_count"] == 3
    assert combined.dims == dims and combined.pl.dims == ("step",)
    np.testing.assert_equal(combined.pl.values, [850.0, 500.0])
    np.testing.assert_equal(combined.isel(time=0).values, np.stack(truth))
    report = QueryReport.from_json(combined.attrs["cedarkit_query_report"])
    assert report.overall["field_count"] == 2


@pytest.mark.parametrize("fn", [ordinary, single])
def test_decode_failure_releases_all_detached_handles(raw, monkeypatch, fn):
    import reki.readers.grib.eccodes.field as kernel

    handles = []
    released = []
    live = set()
    detach = __import__("reki.grib_io", fromlist=["GribHeader"]).GribHeader.detach
    release = ec.codes_release

    def record(self):
        value = detach(self)
        handles.append(value)
        live.add(value)
        return value

    def release_record(m):
        if m in live:
            released.append(m)
            live.remove(m)
        release(m)

    monkeypatch.setattr(
        __import__("reki.grib_io", fromlist=["GribHeader"]).GribHeader, "detach", record
    )
    monkeypatch.setattr(ec, "codes_release", release_record)
    monkeypatch.setattr(
        kernel,
        "create_data_array_from_message",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("decode injected")),
    )
    with pytest.raises(RuntimeError):
        fn(raw, parameter="t", level_type="pl", level="all")
    assert len(handles) == len(released) == 4 and not live


def test_bytes_return_raw_order_and_no_match(raw, monkeypatch):
    from reki.readers.grib.eccodes import (
        load_bytes_from_file,
        create_messages_from_bytes,
        load_message_from_file,
        load_messages_from_file,
    )

    truth = decoded(raw)
    assert load_bytes_from_file(raw, parameter="absent") is None
    assert load_bytes_from_file(raw, parameter="absent", count=1) == truth[0][0]
    handles = create_messages_from_bytes(b"".join(r[0] for r in truth))
    try:
        assert [ec.codes_get_message(m) for m in handles] == [r[0] for r in truth]
    finally:
        for m in handles:
            ec.codes_release(m)
    handles = load_messages_from_file(raw, parameter="t", level_type="pl")
    try:
        assert [ec.codes_get_message(m) for m in handles] == [truth[i][0] for i in (0, 2, 3, 4)]
    finally:
        for m in handles:
            ec.codes_release(m)
    assert load_messages_from_file(raw, parameter="absent") is None
    m = load_message_from_file(raw, parameter="absent", count=1)
    try:
        assert ec.codes_get_message(m) == truth[0][0]
    finally:
        ec.codes_release(m)


@pytest.mark.parametrize("count", [2.0, True])
def test_message_count_requires_an_integer(raw, count):
    from reki.format.grib import load_message_from_file

    with pytest.raises(QueryError) as caught:
        load_message_from_file(raw, count=count)
    assert caught.value.code == "invalid_query"
    assert caught.value.path == "/count"


@pytest.mark.parametrize("fail", [False, True])
def test_byte_reader_releases_selected_message(raw, monkeypatch, fail):
    from reki.format.grib.eccodes import load_bytes_from_file

    expected = decoded(raw)[2][0]
    live = set()
    open_message, release_message = ec.codes_grib_new_from_file, ec.codes_release

    def opened(*args, **kwargs):
        handle = open_message(*args, **kwargs)
        if handle is not None:
            live.add(handle)
        return handle

    def released(handle):
        release_message(handle)
        live.remove(handle)

    def fail_extraction(handle):
        raise RuntimeError("byte extraction failed")

    monkeypatch.setattr(ec, "codes_grib_new_from_file", opened)
    monkeypatch.setattr(ec, "codes_release", released)
    try:
        if fail:
            monkeypatch.setattr(ec, "codes_get_message", fail_extraction)
            with pytest.raises(RuntimeError, match="byte extraction failed"):
                load_bytes_from_file(raw, "t", level_type="pl", level=500)
        else:
            assert load_bytes_from_file(raw, "t", level_type="pl", level=500) == expected
        assert not live
    finally:
        for handle in live:
            release_message(handle)


def test_retired_public_names_and_cfgrib_paths():
    import reki

    assert all(
        not hasattr(reki, n)
        for n in [
            "SourceSpec",
            "FieldQuery",
            "DataNotFoundError",
            "MultipleFieldsMatchedError",
            "from_source_lazily",
        ]
    )
    for name in [
        "reki.format.grib.cfgrib",
        "reki.readers.grib.cfgrib",
        "reki.readers.grib.cfgrib.field",
    ]:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(name)
    with pytest.raises(QueryError):
        reki.from_source("file", "ignored.grib2")
    for fn in [ordinary, single, load_fields_from_file]:
        with pytest.raises(QueryError, match="unsupported"):
            fn("missing.grib2", parameter="t", engine="cfgrib")


def test_scaled_pressure_and_leading_padding(raw, tmp_path):
    # The fixed surface is scaled in Pa; ecCodes' decoded level is in hPa.
    m = ec.codes_new_from_message(decoded(raw)[0][0])
    try:
        ec.codes_set(m, "scaleFactorOfFirstFixedSurface", 1)
        ec.codes_set(m, "scaledValueOfFirstFixedSurface", 850000)
        payload = ec.codes_get_message(m)
    finally:
        ec.codes_release(m)
    path = tmp_path / "scaled.grib2"
    path.write_bytes(b"bulletin header\n" + payload)
    assert single(path, level_type="pl", level=850).pl.item() == 850
    field = single(
        path, level_type="pl", level=850, level_dim="isobaricInPa", lazy=True
    )
    assert field.isobaricInPa.item() == 85000
    np.testing.assert_equal(field.values, decoded(raw)[0][1])


def test_collection_different_grids_and_error_precedence(raw, tmp_path):
    first = decoded(raw)[0][0]
    m = ec.codes_new_from_message(first)
    try:
        ec.codes_set(m, "longitudeOfFirstGridPointInDegrees", 101)
        ec.codes_set(m, "longitudeOfLastGridPointInDegrees", 104)
        ec.codes_set(m, "level", 500)
        changed = ec.codes_get_message(m)
    finally:
        ec.codes_release(m)
    path = tmp_path / "different-grid.grib2"
    path.write_bytes(first + changed)
    with pytest.raises(QueryError, match="incompatible_grid"):
        load_fields_from_file(path, parameter="t")
    path.write_bytes(path.read_bytes() + decoded(raw)[1][0])
    with pytest.raises(QueryError, match="multiple_variables"):
        load_field_from_files([path], None, None, "all")


@pytest.mark.parametrize(
    "failure,code",
    [
        (PermissionError("denied"), "permission_denied"),
        (TimeoutError("late"), "timeout"),
        (OSError("disk failure"), "io_error"),
    ],
)
def test_owned_io_faults_are_structured(raw, monkeypatch, failure, code):
    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr("builtins.open", fail)
    with pytest.raises(SourceError) as caught:
        single(raw, parameter="t")
    assert caught.value.code == code
    assert caught.value.__cause__ is failure


def test_empty_netcdf_has_no_match(tmp_path):
    from reki.readers.netcdf import load_field_from_file

    path = tmp_path / "coordinates-only.nc"
    xr.Dataset(coords={"level": [850]}).to_netcdf(path, engine="scipy")
    with pytest.raises(QueryError) as caught:
        load_field_from_file(path, engine="scipy")
    assert caught.value.code == "no_match"
