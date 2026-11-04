from dataclasses import dataclass, asdict
from typing import Union, Dict, Optional, List

import pytest

from reki.format.grib.eccodes import load_field_from_file


@dataclass
class QueryOption:
    parameter: Union[str, dict]
    level_type: Optional[Union[str, Dict]] = None
    level: Optional[Union[float, Dict]] = None


@dataclass
class TestCase:
    query: QueryOption
    expected_grib_key_count: int


@pytest.mark.parametrize(
    "test_case",
    [
        TestCase(query=QueryOption(parameter="t", level_type="pl", level=850), expected_grib_key_count=109)
    ]
)
def test_short_name(grib2_gfs_basic_file_path, test_case):
    field = load_field_from_file(
        grib2_gfs_basic_file_path,
        **asdict(test_case.query)
    )
    assert field is not None
    assert field.attrs["GRIB_count"] == test_case.expected_grib_key_count


@pytest.mark.parametrize(
    "test_case",
    [
        TestCase(
            query=QueryOption(parameter={
                "discipline": 0,
                "parameterCategory": 16,
                "parameterNumber": 225,
            }, level_type="pl", level=850),
            expected_grib_key_count=790
        )
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
    assert field.attrs["GRIB_count"] == test_case.expected_grib_key_count


@pytest.mark.parametrize(
    "test_case",
    [
        TestCase(
            query=QueryOption(parameter="2t"),
            expected_grib_key_count=25,
        ),
        TestCase(
            query=QueryOption(parameter="2sh"),
            expected_grib_key_count=24,
        ),
        TestCase(
            query=QueryOption(parameter="t", level_type="depthBelowLandLayer", level={"first_level": 0.1, "second_level": 0.4}),
            expected_grib_key_count=465,
        ),
        TestCase(
            query=QueryOption(parameter="vwsh", level_type="heightAboveGroundLayer", level={"first_level": 3000, "second_level": 0}),
            expected_grib_key_count=782,
        ),
    ]
)
def test_native_conditions(grib2_gfs_basic_file_path, test_case):
    field = load_field_from_file(
        grib2_gfs_basic_file_path,
        **asdict(test_case.query)
    )
    assert field is not None
    assert field.attrs["GRIB_count"] == test_case.expected_grib_key_count
