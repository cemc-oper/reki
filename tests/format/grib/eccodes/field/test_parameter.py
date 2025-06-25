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


def test_embedded_short_name(grib2_gfs_basic_file_path):
    test_cases = [
        TestCase(
            query=QueryOption(parameter="DEPR", level_type="pl", level=850),
            expected_grib_key_count=719,
        ),
        TestCase(
            query=QueryOption(parameter={
                "discipline": 0,
                "parameterCategory": 0,
                "parameterNumber": 7,
            }, level_type="pl", level=850),
            expected_grib_key_count=719,
        ),
    ]

    fields = []

    for test_case in test_cases:
        field = load_field_from_file(
            grib2_gfs_basic_file_path,
            **asdict(test_case.query)
        )
        assert field is not None
        assert field.attrs["GRIB_count"] == test_case.expected_grib_key_count
        fields.append(field)

    assert fields[0].attrs["GRIB_count"] == fields[1].attrs["GRIB_count"]



@pytest.mark.parametrize(
    "test_case",
    [
        TestCase(
            query=QueryOption(parameter="t2m"),
            expected_grib_key_count=25,
        ),
        TestCase(
            query=QueryOption(parameter="q2m"),
            expected_grib_key_count=24,
        ),
        TestCase(
            query=QueryOption(parameter="st(10-40)"),
            expected_grib_key_count=465,
        ),
        TestCase(
            query=QueryOption(parameter="shr(0-3000)"),
            expected_grib_key_count=782,
        ),
    ]
)
def test_cemc_name(grib2_gfs_basic_file_path, test_case):
    field = load_field_from_file(
        grib2_gfs_basic_file_path,
        **asdict(test_case.query)
    )
    assert field is not None
    assert field.attrs["GRIB_count"] == test_case.expected_grib_key_count
