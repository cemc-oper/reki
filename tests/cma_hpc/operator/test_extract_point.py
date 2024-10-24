import pytest

from reki.data_finder import find_local_file
from reki.format.grib.eccodes import load_field_from_file
from reki.operator import extract_point


@pytest.fixture
def cma_gfs_grib2_orig_file_path(last_two_day, forecast_time_24h):
    start_time = last_two_day
    forecast_time = forecast_time_24h
    file_path = find_local_file(
        f"cma_gfs_gmf/grib2/orig",
        start_time=start_time,
        forecast_time=forecast_time,
    )
    return file_path


@pytest.fixture
def t_2m_field(cma_gfs_grib2_orig_file_path):
    file_path = cma_gfs_grib2_orig_file_path
    parameter = "2t"

    field = load_field_from_file(
        file_path=file_path,
        parameter=parameter,
    )
    return field


def test_extract_point(t_2m_field):
    data = t_2m_field
    point = extract_point(
        data=data,
        longitude=116.17,
        latitude=39.56,
    )
    assert point.latitude.values.item() == 39.56
    assert point.longitude.values.item() == 116.17


@pytest.mark.parametrize(
    "engine,scheme",
    [
        ("xarray", "linear"),
        ("xarray", "nearest"),
        ("scipy", "linear"),
        ("scipy", "nearest"),
        ("scipy", "splinef2d"),
        ("scipy", "rect_bivariate_spline"),
    ]
)
def test_extract_point_with_engine_and_scheme(t_2m_field, engine, scheme):
    data = t_2m_field
    point = extract_point(
        data=data,
        longitude=116.17,
        latitude=39.56,
        scheme=scheme,
        engine=engine,
    )
    assert point.latitude.values.item() == 39.56
    assert point.longitude.values.item() == 116.17


def test_extract_point_multi_points(t_2m_field):
    data = t_2m_field
    point = extract_point(
        data=data,
        longitude=[115, 116, 117],
        latitude=[40, 39],
    )
    assert point.shape == (2, 3)
    assert list(point.latitude.values) == [40, 39]
    assert list(point.longitude.values) == [115, 116, 117]


@pytest.mark.parametrize(
    "engine,scheme",
    [
        ("xarray", "linear"),
        ("xarray", "nearest"),
        ("scipy", "linear"),
        ("scipy", "nearest"),
        ("scipy", "splinef2d"),
        ("scipy", "rect_bivariate_spline"),
    ]
)
def test_extract_point_multi_points_with_engine_and_scheme(t_2m_field, engine, scheme):
    data = t_2m_field
    point = extract_point(
        data=data,
        longitude=[115, 116, 117],
        latitude=[40, 39],
        scheme=scheme,
        engine=engine,
    )
    assert point.shape == (2, 3)


@pytest.mark.parametrize(
    "engine,scheme",
    [
        ("xarray", "linear"),
        ("xarray", "nearest"),
        ("scipy", "linear"),
        ("scipy", "nearest"),
        ("scipy", "splinef2d"),
        ("scipy", "rect_bivariate_spline"),
    ]
)
def test_extract_point_multi_points_with_engine_and_scheme_lat(t_2m_field, engine, scheme):
    data = t_2m_field
    point = extract_point(
        data=data,
        longitude=[115, 116, 117],
        latitude=[39, 40],
        scheme=scheme,
        engine=engine,
    )
    assert point.shape == (2, 3)