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


def test_number(file_path, forecast_time):
    test_cases = [
        TestCase(query=QueryOption("t", "pl", 850), expected_level_type="pl", expected_level=850),
        TestCase(query=QueryOption("h", "pl", 500.0), expected_level_type="pl", expected_level=500.0),
        TestCase(query=QueryOption("Qv", "index", 0), expected_level_type="level", expected_level=1000),
        TestCase(query=QueryOption("u", "index", 1), expected_level_type="level", expected_level=975),
        TestCase(query=QueryOption("tslb", "index", 2), expected_level_type="level", expected_level=950),
        TestCase(query=QueryOption("q2m", "single", 0), expected_level_type="level", expected_level=0),
    ]

    for test_case in test_cases:
        field = load_field_from_file(
            file_path,
            forecast_time=forecast_time,
            **asdict(test_case.query)
        )
        assert field is not None
        assert field.name == test_case.query.parameter
        assert field.coords[test_case.expected_level_type] == test_case.expected_level


def test_list(file_path, modelvar_file_path, forecast_time):
    test_cases = [
        TestCase(
            query=QueryOption("t", "pl", [1000, 850, 500]),
            expected_level_type="pl", expected_level=[1000, 850, 500]
        ),
        TestCase(
            query=QueryOption("tslb", "index", [0, 1, 2, 3]),
            expected_level_type="level", expected_level=[1000, 975, 950, 925]
        )
    ]

    for test_case in test_cases:
        field = load_field_from_file(
            file_path,
            forecast_time=forecast_time,
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
            query=QueryOption("pi", "ml", [1, 20, 30, 50]),
            expected_level_type="ml", expected_level=[1, 20, 30, 50]
        ),
        TestCase(
            query=QueryOption("Qc", "index", [0, 1, 2, 3]),
            expected_level_type="level", expected_level=[1, 2, 3, 4]
        )
    ]

    for test_case in test_cases:
        field = load_field_from_file(
            modelvar_file_path,
            forecast_time=forecast_time,
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
        1000.0,
        975.0,
        950.0,
        925.0,
        900.0,
        850.0,
        800.0,
        750.0,
        700.0,
        650.0,
        600.0,
        550.0,
        500.0,
        450.0,
        400.0,
        350.0,
        300.0,
        250.0,
        200.0,
        150.0,
        100.0,
        70.0,
        50.0,
        30.0,
        20.0,
        10.0,
    ]


def test_none(file_path, pl_levels, forecast_time):
    test_cases = [
        TestCase(query=QueryOption("u10m", "single", None), expected_level_type="level", expected_level=0),
        TestCase(query=QueryOption("tmn", None, None), expected_level_type="level", expected_level=0)
    ]

    for test_case in test_cases:
        field = load_field_from_file(
            file_path,
            forecast_time=forecast_time,
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
            query=QueryOption("tslb", None, None),
            expected_level_type="level", expected_level=[1000, 975, 950, 925]
        ),
    ]

    for test_case in test_cases:
        field = load_field_from_file(
            file_path,
            forecast_time=forecast_time,
            **asdict(test_case.query)
        )
        assert field is not None
        assert field.name == test_case.query.parameter
        assert np.array_equal(
            np.sort(field.coords[test_case.expected_level_type].values),
            np.sort(test_case.expected_level)
        )
