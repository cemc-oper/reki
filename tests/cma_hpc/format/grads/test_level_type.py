from dataclasses import dataclass, asdict
from typing import Dict, List, Union, Optional

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


def test_embedded_name(file_path, modelvar_file_path, forecast_time):
    test_cases = [
        TestCase(query=QueryOption("t", "pl", 250), expected_level_type="pl", expected_level=250),
        TestCase(query=QueryOption("u", "pl", 10.0), expected_level_type="pl", expected_level=10.0)
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
        TestCase(query=QueryOption("u", "ml", 30), expected_level_type="ml", expected_level=30),
        TestCase(query=QueryOption("w", "ml", 50), expected_level_type="ml", expected_level=50)
    ]

    for test_case in test_cases:
        field = load_field_from_file(
            modelvar_file_path,
            forecast_time=forecast_time,
            **asdict(test_case.query)
        )
        assert field is not None
        assert field.name == test_case.query.parameter
        assert field.coords[test_case.expected_level_type] == test_case.expected_level


def test_index(file_path, forecast_time):
    test_cases = [
        TestCase(query=QueryOption("mslb", "index", 0), expected_level_type="level", expected_level=1000),
        TestCase(query=QueryOption("mslb", "index", 1), expected_level_type="level", expected_level=975),
        TestCase(query=QueryOption("mslb", "index", 2), expected_level_type="level", expected_level=950),
        TestCase(query=QueryOption("mslb", "index", 3), expected_level_type="level", expected_level=925)
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


def test_single(file_path, forecast_time):
    test_cases = [
        TestCase(query=QueryOption("glw", "single", None), expected_level_type="level", expected_level=0),
        TestCase(query=QueryOption("ts", "single", None), expected_level_type="level", expected_level=0)
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


def test_none(file_path, forecast_time):
    test_cases = [
        TestCase(query=QueryOption("rainc", None, None), expected_level_type="level", expected_level=0),
        TestCase(query=QueryOption("qfx", None, None), expected_level_type="level", expected_level=0)
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

