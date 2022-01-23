from dataclasses import dataclass, asdict
from typing import Dict, Union, List, Optional

import pytest
import numpy as np

from reki.format.grib.eccodes import load_field_from_file


@dataclass
class QueryOption:
    parameter: Union[str, Dict] = None
    level_type: Union[str, Dict] = None
    level: Optional[Union[float, str, Dict, List[float]]] = None


@dataclass
class TestCase:
    query: QueryOption
    expected_level_name: str = None
    expected_level: float = None


def test_scalar(file_path, modelvar_file_path):
    test_cases = [
        TestCase(
            query=QueryOption(parameter="t", level_type="pl", level=1.5),
            expected_level_name="pl",
            expected_level=1.5
        ),
        TestCase(
            query=QueryOption(parameter="t", level_type="isobaricInhPa", level=850),
            expected_level_name="isobaricInhPa",
            expected_level=850
        ),
        TestCase(
            query=QueryOption(parameter="TMAX", level_type="heightAboveGround", level=2),
            expected_level_name="heightAboveGround",
            expected_level=2
        ),
    ]

    for test_case in test_cases:
        field = load_field_from_file(
            file_path,
            **asdict(test_case.query)
        )
        assert field is not None
        assert field.coords[test_case.expected_level_name] == test_case.expected_level

    test_cases = [
        TestCase(
            query=QueryOption(
                parameter="u", level_type={"typeOfFirstFixedSurface": 131}, level=10),
            expected_level_name="level_131",
            expected_level=10
        )
    ]
    for test_case in test_cases:
        field = load_field_from_file(
            modelvar_file_path,
            **asdict(test_case.query)
        )
        assert field is not None
        assert field.coords[test_case.expected_level_name] == test_case.expected_level


def test_dict(file_path):
    test_cases = [
        TestCase(
            QueryOption(
                parameter="vwsh",
                level_type="heightAboveGroundLayer",
                level=dict(first_level=1000, second_level=0)
            ),
        ),
        TestCase(
            QueryOption(
                parameter="t",
                level_type="depthBelowLandLayer",
                level=dict(first_level=0.1, second_level=0.4)
            ),
        )
    ]
    for test_case in test_cases:
        field = load_field_from_file(
            file_path,
            **asdict(test_case.query)
        )
        assert field is not None


def test_multi_levels(file_path):
    test_cases = [
        TestCase(
            query=QueryOption(parameter="t", level_type="pl", level=[850, 925, 1000]),
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type="isobaricInhPa", level=[850, 925, 1000]),
        )
    ]
    for test_case in test_cases:
        field = load_field_from_file(
            file_path,
            **asdict(test_case.query)
        )
        assert field is not None
        assert np.array_equal(
            np.sort(field.coords[test_case.query.level_type].values),
            np.sort(test_case.query.level).astype(float)
        )


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
        TestCase(
            query=QueryOption(
                parameter="t",
                level_type="pl",
                level="all"
            ),
            expected_level_name="pl",
            expected_level=pl_levels
        ),
    ]
    for test_case in test_cases:
        field = load_field_from_file(
            file_path,
            **asdict(test_case.query)
        )
        assert field is not None
        assert np.array_equal(
            np.sort(field.coords[test_case.expected_level_name].values),
            np.sort(test_case.expected_level).astype(float)
        )


def test_none_level(file_path):
    test_cases = [
        TestCase(
            query=QueryOption(parameter="t", level_type="pl", level=None),
            expected_level_name="pl",
            expected_level=1000
        ),
        TestCase(
            query=QueryOption(parameter="vwsh", level_type="heightAboveGroundLayer", level=None),
            expected_level_name="heightAboveGroundLayer",
            expected_level=1000
        )
    ]
    for test_case in test_cases:
        field = load_field_from_file(
            file_path,
            **asdict(test_case.query)
        )
        assert field is not None
        assert field.coords[test_case.expected_level_name].values == test_case.expected_level
