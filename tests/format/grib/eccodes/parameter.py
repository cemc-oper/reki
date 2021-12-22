import pytest
from reki.format.grib.eccodes import load_field_from_file
from reki.data_finder import find_local_file


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
