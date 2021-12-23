import pytest

from reki.format.grib.eccodes import load_field_from_file


def test_embedded_level_name(file_path, modelvar_file_path):
    """
    embedded level type:

    * pl
    * surface
    * ml
    """
    parameter = "t"
    level = 850
    level_type = "pl"
    field = load_field_from_file(
        file_path,
        parameter=parameter,
        level_type=level_type,
        level=level
    )
    assert field is not None

    level_type = "sfc"
    field = load_field_from_file(
        file_path,
        parameter=parameter,
        level_type=level_type,
    )
    assert field is not None

    parameter = "u"
    level = 10
    level_type = "ml"
    field = load_field_from_file(
        modelvar_file_path,
        parameter=parameter,
        level_type=level_type,
        level=level
    )
    assert field is not None


def test_type_of_level(file_path):
    # (parameter, level_type, level)
    test_cases = [
        ("t", "isobaricInhPa", 850),
        ("t", "isobaricInPa", 50),
        ("asnow", "surface", None),
        ("tmax", "heightAboveGround", 2),
        ("lcc", "nominalTop", None),
        ("tciwv", "atmosphere", None),
        ("prmsl", "meanSea", None),
        ("t", "depthBelowLandLayer", {"first_level": 0, "second_level": 0.1})
    ]

    for (parameter, level_type, level) in test_cases:
        field = load_field_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level
        )
        assert field is not None


def test_grib_key(modelvar_file_path):
    test_cases = [
        ("u", {"typeOfFirstFixedSurface": 131}, 10)
    ]
    for (parameter, level_type, level) in test_cases:
        field = load_field_from_file(
            modelvar_file_path,
            parameter=parameter,
            level_type=level_type,
            level=level
        )
        assert field is not None
