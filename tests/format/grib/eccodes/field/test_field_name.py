import pytest
from typing import Dict, Union, Optional
from dataclasses import dataclass, asdict

from reki.format.grib.eccodes import load_field_from_file


@dataclass
class QueryOption:
    parameter: Union[str, Dict] = None
    level_type: str = None
    level: float = None
    field_name: Optional[str] = None


@dataclass
class TestCase:
    query: QueryOption
    expected_field_name: str


def test_parameter_string(file_path):
    test_cases = [
        TestCase(
            query=QueryOption(parameter="t", level_type="pl", level=850, field_name=None),
            expected_field_name="t"
        ),
        TestCase(
            query=QueryOption(parameter="t", level_type="pl", level=850, field_name="other_field_name"),
            expected_field_name="other_field_name"
        ),
        TestCase(
            query=QueryOption(parameter="TMP", level_type="pl", level=850, field_name=None),
            expected_field_name="TMP"
        ),
        TestCase(
            query=QueryOption(parameter="TMP", level_type="pl", level=850, field_name="other_field_name"),
            expected_field_name="other_field_name"
        )
    ]

    for test_case in test_cases:
        f = load_field_from_file(
            file_path,
            **asdict(test_case.query)
        )
        assert f is not None
        assert f.name == test_case.expected_field_name


def test_parameter_cemc_param_db(file_path):
    test_cases = [
        TestCase(
            query=QueryOption(parameter="btv", field_name=None),
            expected_field_name="btv"
        ),
        TestCase(
            query=QueryOption(parameter="zs", field_name=None),
            expected_field_name="zs",
        ),
    ]

    for test_case in test_cases:
        f = load_field_from_file(
            file_path,
            **asdict(test_case.query)
        )
        assert f is not None
        assert f.name == test_case.expected_field_name


def test_parameter_dict(file_path):
    test_cases = [
        TestCase(
            query=QueryOption(
                parameter=dict(discipline=0, parameterCategory=2, parameterNumber=224),
                level_type="pl",
                level=850,
                field_name=None,
            ),
            expected_field_name="0_2_224"
        ),
        TestCase(
            query=QueryOption(
                parameter=dict(discipline=0, parameterCategory=2, parameterNumber=224),
                level_type="pl",
                level=850,
                field_name="other_field_name"
            ),
            expected_field_name="other_field_name"
        ),
        TestCase(
            query=QueryOption(
                parameter=dict(discipline=0, parameterCategory=2, parameterNumber=227),
                level_type="sfc",
                field_name=None
            ),
            expected_field_name="0_2_227"
        ),
        TestCase(
            query=QueryOption(
                parameter=dict(discipline=0, parameterCategory=2, parameterNumber=227),
                level_type="sfc",
                field_name="other_field_name"
            ),
            expected_field_name="other_field_name"
        ),
        TestCase(
            query=QueryOption(
                parameter=dict(discipline=0, parameterCategory=5, parameterNumber=4),
                level_type="sfc",
                field_name=None,
            ),
            expected_field_name="ulwrf"
        ),
        TestCase(
            query=QueryOption(
                parameter=dict(discipline=0, parameterCategory=5, parameterNumber=4),
                level_type="sfc",
                field_name="other_field_name",
            ),
            expected_field_name="other_field_name"
        )
    ]

    for test_case in test_cases:
        f = load_field_from_file(
            file_path,
            **asdict(test_case.query),
        )
        assert f is not None
        assert f.name == test_case.expected_field_name
