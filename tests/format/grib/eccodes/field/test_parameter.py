import pytest
from reki.format.grib.eccodes import load_field_from_file


def test_short_name(file_path):
    test_cases = [
        ("t", "pl", 850)
    ]
    for (parameter, level_type, level) in test_cases:
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
    test_cases = [
        ({
            "discipline": 0,
            "parameterCategory": 16,
            "parameterNumber": 225,
        }, "pl", 850)
    ]
    for (parameter, level_type, level) in test_cases:
        field = load_field_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level,
        )
        assert field is not None


def test_embedded_short_name(file_path):
    test_cases = [
        ("DEPR", "pl", 850),
        ({
            "discipline": 0,
            "parameterCategory": 0,
            "parameterNumber": 7,
        }, "pl", 850),
    ]

    fields = []

    for (parameter, level_type, level) in test_cases:
        field = load_field_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level,
        )
        assert field is not None
        fields.append(field)

    assert fields[0].attrs["GRIB_count"] == fields[1].attrs["GRIB_count"]
