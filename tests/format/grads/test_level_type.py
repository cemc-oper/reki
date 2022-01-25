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


def test_embedded_name(file_path, modelvar_file_path):
    test_cases = [
        TestCase(query=QueryOption("t", "pl", 250), expected_level_type="pl", expected_level=250),
        TestCase(query=QueryOption("u", "pl", 0.5), expected_level_type="pl", expected_level=0.5)
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
        TestCase(query=QueryOption("u", "ml", 30), expected_level_type="ml", expected_level=30),
        TestCase(query=QueryOption("w", "ml", 50), expected_level_type="ml", expected_level=50)
    ]

    for test_case in test_cases:
        field = load_field_from_file(
            modelvar_file_path,
            **asdict(test_case.query)
        )
        assert field is not None
        assert field.name == test_case.query.parameter
        assert field.coords[test_case.expected_level_type] == test_case.expected_level


def test_index(file_path):
    test_cases = [
        TestCase(query=QueryOption("tsoil", "index", 0), expected_level_type="level", expected_level=1000),
        TestCase(query=QueryOption("tsoil", "index", 1), expected_level_type="level", expected_level=925),
        TestCase(query=QueryOption("tsoil", "index", 2), expected_level_type="level", expected_level=850),
        TestCase(query=QueryOption("tsoil", "index", 3), expected_level_type="level", expected_level=700)
    ]

    for test_case in test_cases:
        field = load_field_from_file(
            file_path,
            **asdict(test_case.query)
        )
        assert field is not None
        assert field.name == test_case.query.parameter
        assert field.coords[test_case.expected_level_type] == test_case.expected_level


def test_single(file_path):
    test_cases = [
        TestCase(query=QueryOption("tcc", "single", None), expected_level_type="level", expected_level=0),
        TestCase(query=QueryOption("t2mx", "single", None), expected_level_type="level", expected_level=0)
    ]

    for test_case in test_cases:
        field = load_field_from_file(
            file_path,
            **asdict(test_case.query)
        )
        assert field is not None
        assert field.name == test_case.query.parameter
        assert field.coords[test_case.expected_level_type] == test_case.expected_level


def test_none(file_path):
    test_cases = [
        TestCase(query=QueryOption("tcc", None, None), expected_level_type="level", expected_level=0),
        TestCase(query=QueryOption("t2mx", None, None), expected_level_type="level", expected_level=0)
    ]

    for test_case in test_cases:
        field = load_field_from_file(
            file_path,
            **asdict(test_case.query)
        )
        assert field is not None
        assert field.name == test_case.query.parameter
        assert field.coords[test_case.expected_level_type] == test_case.expected_level

