from dataclasses import dataclass, asdict
from typing import Dict, List, Union, Optional

import numpy as np
import pytest

from reki.format.grads import load_field_from_file


@dataclass
class QueryOption:
    parameter: str
    level_type: Optional[str]
    level: Optional[Union[int, float, List]]


@dataclass
class TestCase:
    query: QueryOption
    expected_level_type: str
    expected_level: Union[int, float, List]


def test_number(file_path):
    test_cases = [
        TestCase(query=QueryOption("t", "pl", 850), expected_level_type="pl", expected_level=850),
        TestCase(query=QueryOption("h", "pl", 500.0), expected_level_type="pl", expected_level=500.0),
        TestCase(query=QueryOption("q2", "index", 0), expected_level_type="level", expected_level=1000),
        TestCase(query=QueryOption("u", "index", 1), expected_level_type="level", expected_level=925),
        TestCase(query=QueryOption("tsoil", "index", 2), expected_level_type="level", expected_level=850),
        TestCase(query=QueryOption("q2m", "single", 0), expected_level_type="level", expected_level=0),
    ]

    for test_case in test_cases:
        field = load_field_from_file(
            file_path,
            **asdict(test_case.query)
        )
        assert field is not None
        assert field.name == test_case.query.parameter
        assert field.coords[test_case.expected_level_type] == test_case.expected_level


def test_list(file_path, modelvar_file_path):
    test_cases = [
        TestCase(
            query=QueryOption("t", "pl", [1000, 850, 500]),
            expected_level_type="pl", expected_level=[1000, 850, 500]
        ),
        TestCase(
            query=QueryOption("tsoil", "index", [0, 1, 2, 3]),
            expected_level_type="level", expected_level=[1000, 925, 850, 700]
        )
    ]

    for test_case in test_cases:
        field = load_field_from_file(
            file_path,
            **asdict(test_case.query)
        )
        assert field is not None
        assert field.name == test_case.query.parameter
        assert np.array_equal(
            np.sort(field.coords[test_case.expected_level_type].values),
            np.sort(test_case.expected_level)
        )

    test_cases = [
        TestCase(
            query=QueryOption("pip", "ml", [1, 20, 30, 50]),
            expected_level_type="ml", expected_level=[1, 20, 30, 50]
        ),
        TestCase(
            query=QueryOption("qc", "index", [0, 1, 2, 3]),
            expected_level_type="level", expected_level=[1, 2, 3, 4]
        )
    ]

    for test_case in test_cases:
        field = load_field_from_file(
            modelvar_file_path,
            **asdict(test_case.query)
        )
        assert field is not None
        assert field.name == test_case.query.parameter
        assert np.array_equal(
            np.sort(field.coords[test_case.expected_level_type].values),
            np.sort(test_case.expected_level)
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
        TestCase(query=QueryOption("u10m", "single", None), expected_level_type="level", expected_level=0),
        TestCase(query=QueryOption("tiw", None, None), expected_level_type="level", expected_level=0)
    ]

    for test_case in test_cases:
        field = load_field_from_file(
            file_path,
            **asdict(test_case.query)
        )
        assert field is not None
        assert field.name == test_case.query.parameter
        assert field.coords[test_case.expected_level_type] == test_case.expected_level

    test_cases = [
        TestCase(
            query=QueryOption("t", "pl", None),
            expected_level_type="pl", expected_level=pl_levels
        ),
        TestCase(
            query=QueryOption("tsoil", None, None),
            expected_level_type="level", expected_level=[1000, 925, 850, 700]
        ),
    ]

    for test_case in test_cases:
        field = load_field_from_file(
            file_path,
            **asdict(test_case.query)
        )
        assert field is not None
        assert field.name == test_case.query.parameter
        assert np.array_equal(
            np.sort(field.coords[test_case.expected_level_type].values),
            np.sort(test_case.expected_level)
        )
