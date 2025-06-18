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


def test_embedded_level_name(modelvar_file_path):
    """
    embedded level type:

    * pl
    * surface
    * ml
    """
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
