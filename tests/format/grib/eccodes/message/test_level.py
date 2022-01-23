from dataclasses import dataclass, asdict
from typing import Union, Dict, Optional, List

import pytest
import eccodes
import numpy as np

from reki.format.grib.eccodes import load_message_from_file, load_messages_from_file


@dataclass
class QueryOption:
    parameter: Union[str, dict]
    level_type: Union[str, Dict]
    level: Optional[Union[float, Dict, List]]


@dataclass
class TestCase:
    query: QueryOption
    expected_keys: Optional[Dict] = None


def test_scalar(file_path, modelvar_file_path):
    test_cases = [
        TestCase(
            query=QueryOption(parameter="t", level_type="pl", level=1.5),
            expected_keys=dict(typeOfLevel="isobaricInhPa", level=1)
        ),
        TestCase(
            query=QueryOption(parameter="t", level_type="isobaricInhPa", level=850),
            expected_keys=dict(typeOfLevel="isobaricInhPa", level=850)
        ),
        TestCase(
            query=QueryOption(parameter="tmax", level_type="heightAboveGround", level=2),
            expected_keys=dict(typeOfLevel="heightAboveGround", level=2)
        )
    ]

    for test_case in test_cases:
        message = load_message_from_file(
            file_path,
            **asdict(test_case.query)
        )
        assert message is not None
        for key, expected_value in test_case.expected_keys.items():
            assert eccodes.codes_get(message, key) == expected_value

        eccodes.codes_release(message)

    test_cases = [
        TestCase(
            query=QueryOption(parameter="u", level_type={"typeOfFirstFixedSurface": 131}, level=10),
            expected_keys=dict(typeOfFirstFixedSurface=131, level=10)
        )
    ]
    for test_case in test_cases:
        message = load_message_from_file(
            modelvar_file_path,
            **asdict(test_case.query)
        )
        assert message is not None
        for key, expected_value in test_case.expected_keys.items():
            assert eccodes.codes_get(message, key, ktype=int) == expected_value

        eccodes.codes_release(message)


def test_dict(file_path):
    test_cases = [
        TestCase(
            query=QueryOption(parameter="vwsh", level_type="heightAboveGroundLayer", level={"first_level": 1000, "second_level": 0}),
            expected_keys=dict(typeOfLevel="heightAboveGroundLayer", level=1000)
        ),
        TestCase(
            query=QueryOption(parameter="t", level_type="depthBelowLandLayer", level={"first_level": 0.1, "second_level": 0.4}),
            expected_keys=dict(typeOfLevel="depthBelowLandLayer", level=0)
        )
    ]
    for test_case in test_cases:
        message = load_message_from_file(
            file_path,
            **asdict(test_case.query)
        )
        assert message is not None
        for key, expected_value in test_case.expected_keys.items():
            assert eccodes.codes_get(message, key) == expected_value

        eccodes.codes_release(message)


def test_multi_levels(file_path):
    test_cases = [
        TestCase(query=QueryOption(parameter="t", level_type="pl", level=[850, 925, 1000])),
        TestCase(query=QueryOption(parameter="gh", level_type="isobaricInhPa", level=[850, 925, 1000]))
    ]
    for test_case in test_cases:
        messages = load_messages_from_file(
            file_path,
            **asdict(test_case.query)
        )
        assert len(messages) == len(test_case.query.level)
        assert np.array_equal(
            np.sort([eccodes.codes_get(message, "level", ktype=int) for message in messages]),
            np.sort(test_case.query.level)
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
        TestCase(query=QueryOption(parameter="t", level_type="pl", level=pl_levels)),
    ]
    for test_case in test_cases:
        messages = load_messages_from_file(
            file_path,
            **asdict(test_case.query)
        )
        assert len(messages) == len(test_case.query.level)
        assert np.array_equal(
            np.sort([eccodes.codes_get(message, "level", ktype=int) for message in messages]),
            np.sort([single_level*100 if single_level < 1 else int(single_level) for single_level in test_case.query.level])
        )

        for message in messages:
            eccodes.codes_release(message)


def test_none_level(file_path):
    test_cases = [
        TestCase(
            query=QueryOption(parameter="t", level_type="pl", level=None),
            expected_keys=dict(typeOfLevel="isobaricInhPa", level=1000),
        ),
        TestCase(
            query=QueryOption(parameter="vwsh", level_type="heightAboveGroundLayer", level=None),
            expected_keys=dict(typeOfLevel="heightAboveGroundLayer", level=1000)
        )
    ]
    for test_case in test_cases:
        message = load_message_from_file(
            file_path,
            **asdict(test_case.query)
        )
        assert message is not None
        for key, expected_value in test_case.expected_keys.items():
            assert eccodes.codes_get(message, key) == expected_value

        eccodes.codes_release(message)
