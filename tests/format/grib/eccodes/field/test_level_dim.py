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


def test_pl(file_path):
    test_cases = [
        TestCase(
            query=QueryOption(parameter="t", level_type="pl", level=1.5, level_dim=None),
            expected_level_name="pl",
            expected_level=1.5
        ),
        TestCase(
            query=QueryOption(parameter="t", level_type="pl", level=1.5, level_dim="pl"),
            expected_level_name="pl",
            expected_level=1.5
        ),
        TestCase(
            query=QueryOption(parameter="t", level_type="pl", level=1.5, level_dim="isobaricInhPa"),
            expected_level_name="isobaricInhPa",
            expected_level=1.5
        ),
        TestCase(
            query=QueryOption(parameter="t", level_type="pl", level=1.5, level_dim="isobaricInPa"),
            expected_level_name="isobaricInPa",
            expected_level=150.
        ),
        TestCase(
            query=QueryOption(parameter="t", level_type="pl", level=1.5, level_dim="other_level_string"),
            expected_level_name="other_level_string",
            expected_level=1,
        )  # TODO: use float point?
    ]

    for test_case in test_cases:
        field = load_field_from_file(
            file_path,
            **asdict(test_case.query)
        )
        assert field is not None
        assert field.coords[test_case.expected_level_name].values == test_case.expected_level


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


def test_sfc(file_path):
    test_cases = [
        TestCase(
            query=QueryOption(parameter="t", level_type="sfc", level=None, level_dim=None),
            expected_level_name="sfc",
            expected_level=0,
        ),
        TestCase(
            query=QueryOption(parameter="t", level_type="sfc", level=None, level_dim="sfc"),
            expected_level_name="sfc",
            expected_level=0
        ),
        TestCase(
            query=QueryOption(parameter="t", level_type="sfc", level=None, level_dim="other_level_string"),
            expected_level_name="other_level_string",
            expected_level=0
        ),
    ]

    for test_case in test_cases:
        field = load_field_from_file(
            file_path,
            **asdict(test_case.query)
        )
        assert field is not None
        assert field.coords[test_case.expected_level_name].values == test_case.expected_level


def test_type_of_level(file_path):
    test_cases = [
        TestCase(
            query=QueryOption(parameter="gh", level_type="isobaricInhPa", level=10, level_dim=None),
            expected_level_name="isobaricInhPa",
            expected_level=10
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type="isobaricInhPa", level=10, level_dim="other_level_string"),
            expected_level_name="other_level_string",
            expected_level=10
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type="isobaricInPa", level=50, level_dim=None),
            expected_level_name="isobaricInPa",
            expected_level=50
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type="isobaricInPa", level=50, level_dim="other_level_string"),
            expected_level_name="other_level_string",
            expected_level=50
        ),
        TestCase(
            query=QueryOption(parameter="ulwrf", level_type="nominalTop", level=None, level_dim=None),
            expected_level_name="nominalTop",
            expected_level=0
        ),
        TestCase(
            query=QueryOption(parameter="tmax", level_type="heightAboveGround", level=2, level_dim=None),
            expected_level_name="heightAboveGround",
            expected_level=2
        ),
        TestCase(
            query=QueryOption(parameter="prmsl", level_type="meanSea", level=None, level_dim=None),
            expected_level_name="meanSea",
            expected_level=0
        ),
        TestCase(
            query=QueryOption(parameter="q", level_type="depthBelowLandLayer", level={"first_level": 0.1, "second_level": 0.4}, level_dim=None),
            expected_level_name="depthBelowLandLayer",
            expected_level=0,
        ),
        TestCase(
            query=QueryOption(parameter="t", level_type="depthBelowLandLayer", level={"first_level": 1, "second_level": 2}, level_dim=None),
            expected_level_name="depthBelowLandLayer",
            expected_level=1,
        ),
        TestCase(
            query=QueryOption(parameter="vwsh", level_type="heightAboveGroundLayer", level={"first_level": 1000, "second_level": 0}, level_dim=None),
            expected_level_name="heightAboveGroundLayer",
            expected_level=1000,
        ),
    ]

    for test_case in test_cases:
        field = load_field_from_file(
            file_path,
            **asdict(test_case.query),
        )
        assert field is not None
        assert field.coords[test_case.expected_level_name].values == test_case.expected_level


def test_grib_key_for_pl(file_path):
    test_cases = [
        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level=10, level_dim=None),
            expected_level_name="isobaricInhPa",
            expected_level=10
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level=10, level_dim="pl"),
            expected_level_name="pl",
            expected_level=10
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level=10, level_dim="isobaricInhPa"),
            expected_level_name="isobaricInhPa",
            expected_level=10
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level=10, level_dim="isobaricInPa"),
            expected_level_name="isobaricInPa",
            expected_level=1000
        ),

        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level={"first_level": 150}, level_dim=None),
            expected_level_name="isobaricInhPa",
            expected_level=1,
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level={"first_level": 150}, level_dim="pl"),
            expected_level_name="pl",
            expected_level=1.5,
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level={"first_level": 150}, level_dim="isobaricInhPa"),
            expected_level_name="isobaricInhPa",
            expected_level=1.5,
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level={"first_level": 150}, level_dim="isobaricInPa"),
            expected_level_name="isobaricInPa",
            expected_level=150,
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level={"first_level": 150}, level_dim="other_level_string"),
            expected_level_name="other_level_string",
            expected_level=1,
        ),

        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level={"first_level": 50}, level_dim=None),
            expected_level_name="isobaricInPa",
            expected_level=50
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level={"first_level": 50}, level_dim="pl"),
            expected_level_name="pl",
            expected_level=0.5
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level={"first_level": 50}, level_dim="isobaricInhPa"),
            expected_level_name="isobaricInhPa",
            expected_level=0.5
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level={"first_level": 50}, level_dim="isobaricInPa"),
            expected_level_name="isobaricInPa",
            expected_level=50
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level={"first_level": 50}, level_dim="other_level_string"),
            expected_level_name="other_level_string",
            expected_level=50
        ),
    ]

    for test_case in test_cases:
        field = load_field_from_file(
            file_path,
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
