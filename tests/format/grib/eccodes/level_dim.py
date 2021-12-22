import pytest

from reki.format.grib.eccodes import load_field_from_file


def test_pl(file_path):
    test_cases = [
        ("t", "pl", 1.5, None, "pl", 1.5),
        ("t", "pl", 1.5, "pl", "pl", 1.5),
        ("t", "pl", 1.5, "isobaricInhPa", "isobaricInhPa", 1.5),
        ("t", "pl", 1.5, "isobaricInPa", "isobaricInPa", 150.),
        ("t", "pl", 1.5, "other_level_string", "other_level_string", 1),  # TODO: use float point?
    ]

    for (parameter, level_type, level, level_dim, field_level_dim_name, field_level) in test_cases:
        field = load_field_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level,
            level_dim=level_dim
        )
        assert field is not None
        assert field.coords[field_level_dim_name].values == field_level


def test_ml(modelvar_file_path):
    test_cases = [
        ("gh", "ml", 10, None, "ml", 10),
        ("gh", "ml", 10, "ml", "ml", 10),
        ("gh", "ml", 10, "other_level_string", "other_level_string", 10),
    ]

    for (parameter, level_type, level, level_dim, field_level_dim_name, field_level) in test_cases:
        field = load_field_from_file(
            modelvar_file_path,
            parameter=parameter,
            level_type=level_type,
            level=level,
            level_dim=level_dim
        )
        assert field is not None
        assert field.coords[field_level_dim_name].values == field_level


def test_sfc(file_path):
    test_cases = [
        ("gh", "ml", 10, None, "ml", 10),
        ("gh", "ml", 10, "ml", "ml", 10),
        ("gh", "ml", 10, "other_level_string", "other_level_string", 10),
    ]

    for (parameter, level_type, level, level_dim, field_level_dim_name, field_level) in test_cases:
        field = load_field_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level,
            level_dim=level_dim
        )
        assert field is not None
        assert field.coords[field_level_dim_name].values == field_level


def test_type_of_level(file_path):
    test_cases = [
        ("gh", "isobaricInhPa", 10, None, "isobaricInhPa", 10),
        ("gh", "isobaricInhPa", 10, "other_level_string", "other_level_string", 10),
        ("gh", "isobaricInPa", 50, None, "isobaricInPa", 50),
        ("gh", "isobaricInPa", 50, "other_level_string", "other_level_string", 50),
        ("ulwrf", "nominalTop", None, None, "nominalTop", 0),
        ("tmax", "heightAboveGround", 2, None, "heightAboveGround", 2),
        ("prmsl", "meanSea", None, None, "meanSea", 0),
        ("q", "depthBelowLandLayer", {"first_level": 0.1, "second_level": 0.4}, None, "depthBelowLandLayer", 0),
        ("t", "depthBelowLandLayer", {"first_level": 1, "second_level": 2}, None, "depthBelowLandLayer", 1),
        ("vwsh", "heightAboveGroundLayer", {"first_level": 1000, "second_level": 0}, None, "heightAboveGroundLayer", 1000)
    ]

    for (parameter, level_type, level, level_dim, field_level_dim_name, field_level) in test_cases:
        field = load_field_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level,
            level_dim=level_dim
        )
        assert field is not None
        assert field.coords[field_level_dim_name].values == field_level


def test_grib_key_for_pl(file_path):
    test_cases = [
        ("gh", {"typeOfFirstFixedSurface": "pl"}, 10, None, "isobaricInhPa", 10),
        ("gh", {"typeOfFirstFixedSurface": "pl"}, 10, "pl", "pl", 10),
        ("gh", {"typeOfFirstFixedSurface": "pl"}, 10, "isobaricInhPa", "isobaricInhPa", 10),
        ("gh", {"typeOfFirstFixedSurface": "pl"}, 10, "isobaricInPa", "isobaricInPa", 1000),

        ("gh", {"typeOfFirstFixedSurface": "pl"}, {"first_level": 150}, None, "isobaricInhPa", 1),
        ("gh", {"typeOfFirstFixedSurface": "pl"}, {"first_level": 150}, "pl", "pl", 1.5),
        ("gh", {"typeOfFirstFixedSurface": "pl"}, {"first_level": 150}, "isobaricInhPa", "isobaricInhPa", 1.5),
        ("gh", {"typeOfFirstFixedSurface": "pl"}, {"first_level": 150}, "isobaricInPa", "isobaricInPa", 150),
        ("gh", {"typeOfFirstFixedSurface": "pl"}, {"first_level": 150}, "other_level_string", "other_level_string", 1),

        ("gh", {"typeOfFirstFixedSurface": "pl"}, {"first_level": 50}, None, "isobaricInPa", 50),
        ("gh", {"typeOfFirstFixedSurface": "pl"}, {"first_level": 50}, "pl", "pl", 0.5),
        ("gh", {"typeOfFirstFixedSurface": "pl"}, {"first_level": 50}, "isobaricInhPa", "isobaricInhPa", 0.5),
        ("gh", {"typeOfFirstFixedSurface": "pl"}, {"first_level": 50}, "isobaricInPa", "isobaricInPa", 50),
        ("gh", {"typeOfFirstFixedSurface": "pl"}, {"first_level": 50}, "other_level_string", "other_level_string", 50),
    ]

    for (parameter, level_type, level, level_dim, field_level_dim_name, field_level) in test_cases:
        field = load_field_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level,
            level_dim=level_dim
        )
        assert field is not None
        assert field.coords[field_level_dim_name].values == field_level


def test_grib_key_modelvar(modelvar_file_path):
    test_cases = [
        ("t", {"typeOfFirstFixedSurface": 131}, 10, None, "level_131", 10),
        ("t", {"typeOfFirstFixedSurface": 131}, 10, "ml", "ml", 10),
        ("t", {"typeOfFirstFixedSurface": 131}, 10, "other_level_string", "other_level_string", 10),
    ]

    for (parameter, level_type, level, level_dim, field_level_dim_name, field_level) in test_cases:
        field = load_field_from_file(
            modelvar_file_path,
            parameter=parameter,
            level_type=level_type,
            level=level,
            level_dim=level_dim
        )
        assert field is not None
        assert field.coords[field_level_dim_name].values == field_level
