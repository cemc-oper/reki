import numpy as np
import pytest

from reki.format.grads import load_field_from_file


def test_number(file_path):
    test_cases = [
        ("t", "pl", 850, "pl", 850),
        ("h", "pl", 500.0, "pl", 500.0),
        ("q2", "index", 0, "level", 1000),
        ("u", "index", 1, "level", 925),
        ("tsoil", "index", 2, "level", 850),
        ("q2m", "single", 0, "level", 0)
    ]

    for (parameter, level_type, level, expected_level_name, expected_level) in test_cases:
        field = load_field_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level,
        )
        assert field is not None
        assert field.name == parameter
        assert field.coords[expected_level_name] == expected_level


def test_list(file_path, modelvar_file_path):
    test_cases = [
        ("t", "pl", [1000, 850, 500], "pl", [1000, 850, 500]),
        ("tsoil", "index", [0, 1, 2, 3], "level", [1000, 925, 850, 700])
    ]

    for (parameter, level_type, level, expected_level_name, expected_level) in test_cases:
        field = load_field_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level,
        )
        assert field is not None
        assert field.name == parameter
        assert np.array_equal(
            np.sort(field.coords[expected_level_name].values),
            np.sort(expected_level)
        )

    test_cases = [
        ("pip", "ml", [1, 20, 30, 50], "ml", [1, 20, 30, 50]),
        ("qc", "index", [0, 1, 2, 3], "level", [1, 2, 3, 4])
    ]

    for (parameter, level_type, level, expected_level_name, expected_level) in test_cases:
        field = load_field_from_file(
            modelvar_file_path,
            parameter=parameter,
            level_type=level_type,
            level=level,
        )
        assert field is not None
        assert field.name == parameter
        assert np.array_equal(
            np.sort(field.coords[expected_level_name].values),
            np.sort(expected_level)
        )


@pytest.fixture
def pl_levels():
    return [
        1000,
        925,
        850,
        700,
        600,
        500,
        400,
        300,
        250,
        200,
        150,
        100,
        70,
        50,
        30,
        20,
        10,
        7,
        5,
        3,
        2,
        1,
        0.7,
        0.5,
        0.3,
        0.2,
        0.1
    ]


def test_none(file_path, pl_levels):
    test_cases = [
        ("u10m", "single", None, "level", 0),
        ("tiw", None, None, "level", 0)
    ]

    for (parameter, level_type, level, expected_level_name, expected_level) in test_cases:
        field = load_field_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level,
        )
        assert field is not None
        assert field.name == parameter
        assert field.coords[expected_level_name] == expected_level

    test_cases = [
        ("t", "pl", None, "pl", pl_levels),
        ("tsoil", None, None, "level", [1000, 925, 850, 700]),
    ]

    for (parameter, level_type, level, expected_level_name, expected_level) in test_cases:
        field = load_field_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level,
        )
        assert field is not None
        assert field.name == parameter
        assert np.array_equal(
            np.sort(field.coords[expected_level_name].values),
            np.sort(expected_level)
        )
