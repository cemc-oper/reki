from dataclasses import dataclass, asdict
from typing import Union, Dict, Optional, List

import pytest

from reki.format.grib.eccodes import load_field_from_file


@dataclass
class QueryOption:
    parameter: Union[str, dict]
    level_type: Union[str, Dict]
    level: Optional[Union[float, Dict]]


@dataclass
class TestCase:
    query: QueryOption


@pytest.mark.parametrize(
    "test_case",
    [
        TestCase(query=QueryOption(parameter="t", level_type="pl", level=850))
    ]
)
def test_short_name(grib2_gfs_basic_file_path, test_case):
    field = load_field_from_file(
        grib2_gfs_basic_file_path,
        **asdict(test_case.query)
    )
    assert field is not None


@pytest.mark.parametrize(
    "test_case",
    [
        TestCase(query=QueryOption(parameter={
            "discipline": 0,
            "parameterCategory": 16,
            "parameterNumber": 225,
        }, level_type="pl", level=850))
    ]
)
def test_numbers(grib2_gfs_basic_file_path, test_case):
    """
    雷达组合反射率
    """
    field = load_field_from_file(
        grib2_gfs_basic_file_path,
        **asdict(test_case.query)
    )
    assert field is not None


def test_embedded_short_name(grib2_gfs_basic_file_path):
    test_cases = [
        TestCase(query=QueryOption(parameter="DEPR", level_type="pl", level=850)),
        TestCase(query=QueryOption(parameter={
            "discipline": 0,
            "parameterCategory": 0,
            "parameterNumber": 7,
        }, level_type="pl", level=850)),
    ]

    fields = []

    for test_case in test_cases:
        field = load_field_from_file(
            grib2_gfs_basic_file_path,
            **asdict(test_case.query)
        )
        assert field is not None
        fields.append(field)

    assert fields[0].attrs["GRIB_count"] == fields[1].attrs["GRIB_count"]
