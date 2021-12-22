import pytest
import numpy as np

from reki.format.grib.eccodes import load_field_from_file


def test_scalar(file_path, modelvar_file_path):
    test_cases = [
        ("t", "pl", 1.5),
        ("t", "isobaricInhPa", 850),
        ("tmax", "heightAboveGround", 2)
    ]

    for (parameter, level_type, level) in test_cases:
        field = load_field_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level
        )
        assert field is not None
        assert field.coords[level_type] == level

    test_cases = [
        ("u", {"typeOfFirstFixedSurface": 131}, 10, "level_131")
    ]
    for (parameter, level_type, level, level_dim_name) in test_cases:
        field = load_field_from_file(
            modelvar_file_path,
            parameter=parameter,
            level_type=level_type,
            level=level
        )
        assert field is not None
        assert field.coords[level_dim_name] == level


def test_dict(file_path):
    test_cases = [
        ("vwsh", "heightAboveGroundLayer", {"first_level": 1000, "second_level": 0}),
        ("t", "depthBelowLandLayer", {"first_level": 0.1, "second_level": 0.4})
    ]
    for (parameter, level_type, level) in test_cases:
        field = load_field_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level
        )
        assert field is not None


def test_multi_levels(file_path):
    test_cases = [
        ("t", "pl", [850, 925, 1000]),
        ("gh", "isobaricInhPa", [850, 925, 1000])
    ]
    for (parameter, level_type, level) in test_cases:
        field = load_field_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level
        )
        assert field is not None
        assert np.array_equal(np.sort(field.coords[level_type].values), np.sort(level).astype(float))


@pytest.fixture
def pl_levels():
    return [
        1000,
        975,
        950,
        925,
        900,
        850,
        800,
        750,
        700,
        650,
        600,
        550,
        500,
        450,
        400,
        350,
        300,
        275,
        250,
        225,
        200,
        175,
        150,
        125,
        100,
        70,
        50,
        30,
        20,
        10,
        7,
        5,
        4,
        3,
        2,
        1.5,
        1,
        0.5,
        0.2,
        0.1
    ]


def test_all_levels(file_path, pl_levels):
    test_cases = [
        ("t", "pl", pl_levels),
    ]
    for (parameter, level_type, level) in test_cases:
        field = load_field_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level="all"
        )
        assert field is not None
        assert np.array_equal(np.sort(field.coords[level_type].values), np.sort(level).astype(float))


def test_none_level(file_path):
    test_cases = [
        ("t", "pl", 1000),
        ("vwsh", "heightAboveGroundLayer", 1000)
    ]
    for (parameter, level_type, level) in test_cases:
        field = load_field_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=None
        )
        assert field is not None
        assert field.coords[level_type].values == level
