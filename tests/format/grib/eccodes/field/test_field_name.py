import pytest

from reki.format.grib.eccodes import load_field_from_file


def test_parameter_string(file_path):
    test_cases = [
        (dict(parameter="t", level_type="pl", level=850), None, "t"),
        (dict(parameter="t", level_type="pl", level=850), "other_field_name", "other_field_name"),

        (dict(parameter="TMP", level_type="pl", level=850), None, "TMP"),
        (dict(parameter="TMP", level_type="pl", level=850), "other_field_name", "other_field_name"),
    ]

    for (filters, field_name, expected_name) in test_cases:
        field = load_field_from_file(
            file_path,
            **filters,
            field_name=field_name,
        )
        assert field is not None
        assert field.name == expected_name


def test_parameter_dict(file_path):
    test_cases = [
        (dict(
            parameter=dict(discipline=0, parameterCategory=2, parameterNumber=224),
            level_type="pl", level=850,
        ), None, "0_2_224"),
        (dict(
            parameter=dict(discipline=0, parameterCategory=2, parameterNumber=224),
            level_type="pl", level=850,
        ), "other_field_name", "other_field_name"),

        (dict(
            parameter=dict(discipline=0, parameterCategory=2, parameterNumber=227),
            level_type="sfc"
        ), None, "0_2_227"),
        (dict(
            parameter=dict(discipline=0, parameterCategory=2, parameterNumber=227),
            level_type="sfc"
        ), "other_field_name", "other_field_name"),

        (dict(
            parameter=dict(discipline=0, parameterCategory=5, parameterNumber=4),
            level_type="sfc"
        ), None, "ulwrf"),
        (dict(
            parameter=dict(discipline=0, parameterCategory=5, parameterNumber=4),
            level_type="sfc"
        ), "other_field_name", "other_field_name"),
    ]

    for (filters, field_name, expected_name) in test_cases:
        field = load_field_from_file(
            file_path,
            **filters,
            field_name=field_name,
        )
        assert field is not None
        assert field.name == expected_name
