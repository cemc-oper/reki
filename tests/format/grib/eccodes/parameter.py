import pytest
from reki.format.grib.eccodes import load_field_from_file
from reki.data_finder import find_local_file


@pytest.fixture
def system_name():
    return "grapes_gfs_gmf"


@pytest.fixture
def file_path(system_name, start_time, forecast_time, storage_base):
    f = find_local_file(
        f"{system_name}/grib2/orig",
        start_time=start_time,
        forecast_time=forecast_time,
        storage_base=storage_base
    )
    return f


def test_short_name(file_path):
    parameter = "t"
    level_type = "pl"
    level = 850
    field = load_field_from_file(
        file_path,
        parameter=parameter,
        level_type=level_type,
        level=level,
    )
    assert field is not None


def test_numbers(file_path):
    """
    雷达组合反射率
    """
    parameter = {
        "discipline": 0,
        "parameterCategory": 16,
        "parameterNumber": 225,
    }
    level_type = "pl"
    level = 850
    field = load_field_from_file(
        file_path,
        parameter=parameter,
        level_type=level_type,
        level=level,
    )
    assert field is not None


def test_embedded_short_name(file_path):
    parameter = "DEPR"
    level_type = "pl"
    level = 850
    field = load_field_from_file(
        file_path,
        parameter=parameter,
        level_type=level_type,
        level=level,
    )
    assert field is not None

    parameter = {
        "discipline": 0,
        "parameterCategory": 0,
        "parameterNumber": 7,
    }
    field_numbers = load_field_from_file(
        file_path,
        parameter=parameter,
        level_type=level_type,
        level=level,
    )
    assert field.attrs["GRIB_count"] == field_numbers.attrs["GRIB_count"]
