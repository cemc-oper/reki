"""Small SYNTHETIC regular-ll grids; expected axes are authored independently.

ecCodes 2.48 Regular/Latlon iterator implementations define the expected axes.
The 1e-12 assertion bound concerns floating representation of these literals,
not a business-grid or encoded-header consistency tolerance.
"""

from copy import deepcopy

import eccodes
import numpy as np
import pytest

from cedarkit_query import SourceError
from reki import from_source
from reki.translation.grib_backend import _grid

CASES = [
    ("exact", {}, [], [50, 49, 48], [100, 101, 102, 103]),
    (
        "latitude_residual_plus2",
        {"latitudeOfLastGridPoint": 48000002},
        [],
        [50, 49, 48.000002],
        [100, 101, 102, 103],
    ),
    (
        "residual_minus5_plus9",
        {"latitudeOfLastGridPoint": 47999995, "longitudeOfLastGridPoint": 103000009},
        [],
        [50, 49, 47.999995],
        [100, 101.000003, 102.000006, 103.000009],
    ),
    (
        "missing_j_increment",
        {"latitudeOfLastGridPoint": 48000002},
        ["jDirectionIncrement"],
        [50, 49.000001, 48.000002],
        [100, 101, 102, 103],
    ),
    (
        "missing_i_increment",
        {},
        ["iDirectionIncrement"],
        [50, 49, 48],
        [100, 101, 102, 103],
    ),
    (
        "negative_i",
        {
            "iScansNegatively": 1,
            "longitudeOfFirstGridPoint": 103000000,
            "longitudeOfLastGridPoint": 100000000,
        },
        [],
        [50, 49, 48],
        [103, 102, 101, 100],
    ),
    (
        "positive_j",
        {
            "jScansPositively": 1,
            "latitudeOfFirstGridPoint": 48000000,
            "latitudeOfLastGridPoint": 50000000,
        },
        [],
        [48, 49, 50],
        [100, 101, 102, 103],
    ),
    (
        "negative_i_positive_j",
        {
            "iScansNegatively": 1,
            "jScansPositively": 1,
            "latitudeOfFirstGridPoint": 48000000,
            "latitudeOfLastGridPoint": 50000000,
            "longitudeOfFirstGridPoint": 103000000,
            "longitudeOfLastGridPoint": 100000000,
        },
        [],
        [48, 49, 50],
        [103, 102, 101, 100],
    ),
    (
        "positive_i_wrap",
        {"longitudeOfFirstGridPoint": 359000000, "longitudeOfLastGridPoint": 2000000},
        [],
        [50, 49, 48],
        [-1, 0, 1, 2],
    ),
    (
        "negative_i_wrap",
        {
            "iScansNegatively": 1,
            "longitudeOfFirstGridPoint": 1000000,
            "longitudeOfLastGridPoint": 358000000,
        },
        [],
        [50, 49, 48],
        [1, 0, -1, 358],
    ),
    (
        "single_i",
        {"Ni": 1, "longitudeOfLastGridPoint": 100000000},
        [],
        [50, 49, 48],
        [100],
    ),
    (
        "single_j",
        {"Nj": 1, "latitudeOfLastGridPoint": 50000000},
        [],
        [50],
        [100, 101, 102, 103],
    ),
    (
        "custom_angular_unit",
        {
            "basicAngleOfTheInitialProductionDomain": 1,
            "subdivisionsOfBasicAngle": 1000,
            "latitudeOfFirstGridPoint": 50000,
            "latitudeOfLastGridPoint": 48000,
            "longitudeOfFirstGridPoint": 100000,
            "longitudeOfLastGridPoint": 103000,
            "iDirectionIncrement": 1000,
            "jDirectionIncrement": 1000,
        },
        [],
        [50, 49, 48],
        [100, 101, 102, 103],
    ),
]


def write_synthetic_grid(path, case):
    _, changes, missing, _, _ = deepcopy(case)
    settings = {
        "Ni": 4,
        "Nj": 3,
        "dataDate": 20260101,
        "dataTime": 0,
        "forecastTime": 0,
        "iScansNegatively": 0,
        "jScansPositively": 0,
        "latitudeOfFirstGridPoint": 50000000,
        "latitudeOfLastGridPoint": 48000000,
        "longitudeOfFirstGridPoint": 100000000,
        "longitudeOfLastGridPoint": 103000000,
        "iDirectionIncrement": 1000000,
        "jDirectionIncrement": 1000000,
    }
    settings.update(changes)
    # Angular scaling is established before setting its encoded coordinates.
    ordered = {
        k: settings.pop(k)
        for k in ("basicAngleOfTheInitialProductionDomain", "subdivisionsOfBasicAngle")
        if k in settings
    }
    ordered.update(settings)
    handle = eccodes.codes_grib_new_from_samples("regular_ll_sfc_grib2")
    try:
        for key, value in ordered.items():
            eccodes.codes_set_long(handle, key, value)
        for key in missing:
            eccodes.codes_set_missing(handle, key)
        eccodes.codes_set_values(
            handle, np.arange(settings["Ni"] * settings["Nj"], dtype=float)
        )
        with path.open("wb") as stream:
            eccodes.codes_write(handle, stream)
    finally:
        eccodes.codes_release(handle)
    return path


def inspect_synthetic(path):
    with path.open("rb") as stream:
        handle = eccodes.codes_grib_new_from_file(stream, headers_only=True)
    try:
        grid, lat, lon, shape = _grid(handle)
        raw = {
            key: eccodes.codes_get_long(handle, key)
            for key in (
                "Ni",
                "Nj",
                "scanningMode",
                "latitudeOfFirstGridPoint",
                "latitudeOfLastGridPoint",
                "longitudeOfFirstGridPoint",
                "longitudeOfLastGridPoint",
                "basicAngleOfTheInitialProductionDomain",
                "subdivisionsOfBasicAngle",
            )
        }
        return {
            "grid": grid,
            "latitude": lat.tolist(),
            "longitude": lon.tolist(),
            "shape": list(shape),
            "raw": raw,
        }
    finally:
        eccodes.codes_release(handle)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c[0])
def test_synthetic_coordinate_axes_do_not_request_field_values(
    tmp_path, monkeypatch, case
):
    path = write_synthetic_grid(tmp_path / "SYNTHETIC.axes.grib2", case)
    original = eccodes.codes_get_double_array
    requested = []

    def guarded(handle, key):
        assert key in {"latitudes", "longitudes"}
        requested.append(key)
        return original(handle, key)

    monkeypatch.setattr(eccodes, "codes_get_double_array", guarded)
    actual = inspect_synthetic(path)
    np.testing.assert_allclose(actual["latitude"], case[3], rtol=0, atol=1e-12)
    np.testing.assert_allclose(actual["longitude"], case[4], rtol=0, atol=1e-12)
    assert requested == ["latitudes", "longitudes"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c[0])
def test_synthetic_query_output_keeps_scan_order_and_value_pairing(tmp_path, case):
    path = write_synthetic_grid(tmp_path / "SYNTHETIC.output.grib2", case)
    with from_source({"kind": "file", "path": str(path)}) as source:
        result = (
            source.sel(native={"grib": {"parameterNumber": 0}})
            .all()
            .to_xarray(rename="synthetic_grid")
        )
    np.testing.assert_allclose(result.latitude.values, case[3], rtol=0, atol=1e-12)
    np.testing.assert_allclose(result.longitude.values, case[4], rtol=0, atol=1e-12)
    expected = np.arange(len(case[3]) * len(case[4])).reshape(
        len(case[3]), len(case[4])
    )
    np.testing.assert_array_equal(
        result.synthetic_grid.values.reshape(expected.shape), expected
    )


@pytest.mark.parametrize("coordinate", ["latitudes", "longitudes"])
@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
def test_nonfinite_coordinate_is_metadata_error_not_an_accepted_axis(
    tmp_path, monkeypatch, coordinate, value
):
    path = write_synthetic_grid(tmp_path / "SYNTHETIC.nonfinite.grib2", CASES[0])
    original = eccodes.codes_get_double_array

    def broken(handle, key):
        raw = original(handle, key)
        return np.full_like(raw, value) if key == coordinate else raw

    monkeypatch.setattr(eccodes, "codes_get_double_array", broken)
    with pytest.raises(SourceError) as exc:
        inspect_synthetic(path)
    assert exc.value.context["reason"] == "inconsistent_native_metadata"


@pytest.mark.parametrize("flag", ["jPointsAreConsecutive", "alternativeRowScanning"])
def test_unimplemented_scan_layout_fails_before_coordinates(
    tmp_path, monkeypatch, flag
):
    case = ("SYNTHETIC.scan", {flag: 1}, [], [], [])
    path = write_synthetic_grid(tmp_path / "SYNTHETIC.scan.grib2", case)

    def forbidden(*args):
        raise AssertionError("unsupported scan requested coordinates")

    monkeypatch.setattr(eccodes, "codes_get_double_array", forbidden)
    with pytest.raises(SourceError) as exc:
        inspect_synthetic(path)
    assert exc.value.context["reason"] == "unsupported_native_encoding"
