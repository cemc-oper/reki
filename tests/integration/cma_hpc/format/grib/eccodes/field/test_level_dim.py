from dataclasses import dataclass, asdict
from typing import List, Dict, Union, Optional

import pytest

from reki.format.grib.eccodes import load_field_from_file


@dataclass
class QueryOption:
    parameter: str
    level_type: Union[str, Dict]
    level: Optional[Union[float, Dict]]
    level_dim: Optional[str] = None


@dataclass
class TestCase:
    query: QueryOption
    expected_level_name: Optional[str]
    expected_level: float



def test_ml(modelvar_file_path):
    test_cases = [
        TestCase(
            query=QueryOption(parameter="gh", level_type="ml", level=10, level_dim=None),
            expected_level_name="ml",
            expected_level=10
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type="ml", level=10, level_dim="ml"),
            expected_level_name="ml",
            expected_level=10,
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type="ml", level=10, level_dim="other_level_string"),
            expected_level_name="other_level_string",
            expected_level=10,
        ),
    ]

    for test_case in test_cases:
        field = load_field_from_file(
            modelvar_file_path,
            **asdict(test_case.query)
        )
        assert field is not None
        assert field.coords[test_case.expected_level_name].values == test_case.expected_level


def test_grib_key_modelvar(modelvar_file_path):
    test_cases = [
        TestCase(
            query=QueryOption(parameter="t", level_type={"typeOfFirstFixedSurface": 131}, level=10, level_dim=None),
            expected_level_name="level_131",
            expected_level=10,
        ),
        TestCase(
            query=QueryOption(parameter="t", level_type={"typeOfFirstFixedSurface": 131}, level=10, level_dim="ml"),
            expected_level_name="ml",
            expected_level=10,
        ),
        TestCase(
            query=QueryOption(parameter="t", level_type={"typeOfFirstFixedSurface": 131}, level=10, level_dim="other_level_string"),
            expected_level_name="other_level_string",
            expected_level=10,
        ),
    ]

    for test_case in test_cases:
        field = load_field_from_file(
            modelvar_file_path,
            **asdict(test_case.query)
        )
        assert field is not None
        assert field.coords[test_case.expected_level_name].values == test_case.expected_level
