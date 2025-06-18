from dataclasses import dataclass, asdict
from typing import Dict, Union, List, Optional

import pytest
import numpy as np

from reki.format.grib.eccodes import load_field_from_file


@dataclass
class QueryOption:
    parameter: Optional[Union[str, Dict]] = None
    level_type: Optional[Union[str, Dict]] = None
    level: Optional[Union[float, str, Dict, List[float]]] = None


@dataclass
class TestCase:
    query: QueryOption
    expected_level_name: Optional[str] = None
    expected_level: Optional[float] = None


def test_scalar(modelvar_file_path):
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