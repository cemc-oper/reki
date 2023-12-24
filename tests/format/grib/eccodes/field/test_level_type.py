from dataclasses import dataclass, asdict
from typing import Union, Dict, Optional, List

import pytest

from reki.format.grib.eccodes import load_field_from_file


@dataclass
class QueryOption:
    parameter: str
    level_type: Union[str, Dict]
    level: Optional[Union[float, Dict]]


@dataclass
class TestCase:
    query: QueryOption


def test_embedded_level_name(file_path, modelvar_file_path):
    """
    embedded level type:

    * pl
    * surface
    * ml
    """
    test_cases = [
        TestCase(
            query=QueryOption(parameter="t", level_type="pl", level=850),
        ),
        TestCase(
            query=QueryOption(parameter="t", level_type="sfc", level=None),
        ),
    ]
    for test_case in test_cases:
        field = load_field_from_file(
            file_path,
            **asdict(test_case.query)
        )
        assert field is not None

    test_cases = [
        TestCase(
            query=QueryOption(parameter="u", level_type="ml", level=10)
        )
    ]
    for test_case in test_cases:
        field = load_field_from_file(
            modelvar_file_path,
            **asdict(test_case.query)
        )
        assert field is not None


def test_type_of_level(file_path):
    test_cases = [
        TestCase(query=QueryOption(parameter="t", level_type="isobaricInhPa", level=850)),
        TestCase(query=QueryOption(parameter="t", level_type="isobaricInPa", level=50)),
        TestCase(query=QueryOption(parameter="acpcp", level_type="surface", level=None)),
        TestCase(query=QueryOption(parameter="tmax", level_type="heightAboveGround", level=2)),
        TestCase(query=QueryOption(parameter="lcc", level_type="entireAtmosphere", level=None)),
        TestCase(query=QueryOption(parameter="ulwrf", level_type="nominalTop", level=None)),
        TestCase(query=QueryOption(parameter="pwat", level_type="atmosphere", level=None)),
        TestCase(query=QueryOption(parameter="prmsl", level_type="meanSea", level=None)),
        TestCase(query=QueryOption(parameter="t", level_type="depthBelowLandLayer", level={"first_level": 0, "second_level": 0.1})),
        TestCase(query=QueryOption(parameter="vwsh", level_type="heightAboveGroundLayer", level=1000))
    ]

    for test_case in test_cases:
        field = load_field_from_file(
            file_path,
            **asdict(test_case.query)
        )
        assert field is not None


def test_grib_key(modelvar_file_path):
    test_cases = [
        TestCase(query=QueryOption(parameter="u", level_type={"typeOfFirstFixedSurface": 131}, level=10))
    ]
    for test_case in test_cases:
        field = load_field_from_file(
            modelvar_file_path,
            **asdict(test_case.query)
        )
        assert field is not None
