import pytest
import eccodes
import numpy as np

from reki.format.grib.eccodes import load_message_from_file, load_messages_from_file


def test_scalar(file_path, modelvar_file_path):
    test_cases = [
        ("t", "pl", 1.5, dict(typeOfLevel="isobaricInhPa", level=1)),
        ("t", "isobaricInhPa", 850, dict(typeOfLevel="isobaricInhPa", level=850)),
        ("tmax", "heightAboveGround", 2, dict(typeOfLevel="heightAboveGround", level=2))
    ]

    for (parameter, level_type, level, expected_keys) in test_cases:
        message = load_message_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level
        )
        assert message is not None
        for key, expected_value in expected_keys.items():
            assert eccodes.codes_get(message, key) == expected_value

        eccodes.codes_release(message)

    test_cases = [
        ("u", {"typeOfFirstFixedSurface": 131}, 10, dict(typeOfFirstFixedSurface=131, level=10))
    ]
    for (parameter, level_type, level, expected_keys) in test_cases:
        message = load_message_from_file(
            modelvar_file_path,
            parameter=parameter,
            level_type=level_type,
            level=level
        )
        assert message is not None
        for key, expected_value in expected_keys.items():
            assert eccodes.codes_get(message, key, ktype=int) == expected_value

        eccodes.codes_release(message)


def test_dict(file_path):
    test_cases = [
        ("vwsh", "heightAboveGroundLayer", {"first_level": 1000, "second_level": 0},
         dict(typeOfLevel="heightAboveGroundLayer", level=1000)),
        ("t", "depthBelowLandLayer", {"first_level": 0.1, "second_level": 0.4},
         dict(typeOfLevel="depthBelowLandLayer", level=0))
    ]
    for (parameter, level_type, level, expected_keys) in test_cases:
        message = load_message_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level
        )
        assert message is not None
        for key, expected_value in expected_keys.items():
            assert eccodes.codes_get(message, key) == expected_value

        eccodes.codes_release(message)


def test_multi_levels(file_path):
    test_cases = [
        ("t", "pl", [850, 925, 1000]),
        ("gh", "isobaricInhPa", [850, 925, 1000])
    ]
    for (parameter, level_type, level) in test_cases:
        messages = load_messages_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level
        )
        assert len(messages) == len(level)
        assert np.array_equal(
            np.sort([eccodes.codes_get(message, "level", ktype=int) for message in messages]),
            np.sort(level)
        )

        for message in messages:
            eccodes.codes_release(message)


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
        messages = load_messages_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=None,
        )
        assert len(messages) == len(level)
        assert np.array_equal(
            np.sort([eccodes.codes_get(message, "level", ktype=int) for message in messages]),
            np.sort([single_level*100 if single_level < 1 else int(single_level) for single_level in level])
        )

        for message in messages:
            eccodes.codes_release(message)


def test_none_level(file_path):
    test_cases = [
        ("t", "pl", dict(typeOfLevel="isobaricInhPa", level=1000)),
        ("vwsh", "heightAboveGroundLayer", dict(typeOfLevel="heightAboveGroundLayer", level=1000))
    ]
    for (parameter, level_type, expected_keys) in test_cases:
        message = load_message_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=None
        )
        assert message is not None
        for key, expected_value in expected_keys.items():
            assert eccodes.codes_get(message, key) == expected_value

        eccodes.codes_release(message)
