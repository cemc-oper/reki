import pytest
from typing import Dict, Union, Optional
from dataclasses import dataclass, asdict

from reki.format.grib.eccodes import load_field_from_file


@dataclass
class QueryOption:
    parameter: Optional[Union[str, Dict]] = None
    level_type: Optional[str] = None
    level: Optional[float] = None
    field_name: Optional[str] = None


@dataclass
class TestCase:
    query: QueryOption
    expected_grib_key_count: int
    expected_field_name: str


@pytest.mark.parametrize(
    "test_case",
    [
        TestCase(
            query=QueryOption(parameter="t", level_type="pl", level=850, field_name=None),
            expected_grib_key_count=109,
            expected_field_name="t",
        ),
        TestCase(
            query=QueryOption(parameter="t", level_type="pl", level=850, field_name="other_field_name"),
            expected_grib_key_count=109,
            expected_field_name="other_field_name",
        ),
        TestCase(
            query=QueryOption(parameter="TMP", level_type="pl", level=850, field_name=None),
            expected_grib_key_count=109,
            expected_field_name="TMP",
        ),
        TestCase(
            query=QueryOption(parameter="TMP", level_type="pl", level=850, field_name="other_field_name"),
            expected_grib_key_count=109,
            expected_field_name="other_field_name",
        )
    ]
)
def test_parameter_string(grib2_gfs_basic_file_path, test_case):
    f = load_field_from_file(
        grib2_gfs_basic_file_path,
        **asdict(test_case.query)
    )
    assert f is not None
    assert f.name == test_case.expected_field_name
    assert f.attrs["GRIB_count"] == test_case.expected_grib_key_count



@pytest.mark.parametrize(
    "test_case",
    [
        TestCase(
            query=QueryOption(parameter="btv", field_name=None),
            expected_grib_key_count=861,
            expected_field_name="btv"
        ),
        TestCase(
            query=QueryOption(parameter="zs", field_name=None),
            expected_grib_key_count=23,
            expected_field_name="zs",
        ),
    ]
)
def test_parameter_cemc_param_db(grib2_gfs_basic_file_path, test_case):
    f = load_field_from_file(
        grib2_gfs_basic_file_path,
        **asdict(test_case.query)
    )
    assert f is not None
    assert f.name == test_case.expected_field_name
    assert f.attrs["GRIB_count"] == test_case.expected_grib_key_count


@pytest.mark.parametrize(
    "test_case",
    [
        TestCase(
            query=QueryOption(
                parameter=dict(discipline=0, parameterCategory=2, parameterNumber=224),
                level_type="pl",
                level=850,
                field_name=None,
            ),
            expected_grib_key_count=599,
            expected_field_name="0_2_224"
        ),
        TestCase(
            query=QueryOption(
                parameter=dict(discipline=0, parameterCategory=2, parameterNumber=224),
                level_type="pl",
                level=850,
                field_name="other_field_name"
            ),
            expected_grib_key_count=599,
            expected_field_name="other_field_name"
        ),
        TestCase(
            query=QueryOption(
                parameter=dict(discipline=0, parameterCategory=2, parameterNumber=227),
                level_type="sfc",
                field_name=None
            ),
            expected_grib_key_count=36,
            expected_field_name="0_2_227"
        ),
        TestCase(
            query=QueryOption(
                parameter=dict(discipline=0, parameterCategory=2, parameterNumber=227),
                level_type="sfc",
                field_name="other_field_name"
            ),
            expected_grib_key_count=36,
            expected_field_name="other_field_name"
        ),
        TestCase(
            query=QueryOption(
                parameter=dict(discipline=0, parameterCategory=5, parameterNumber=4),
                level_type="sfc",
                field_name=None,
            ),
            expected_grib_key_count=10,
            expected_field_name="sulwrf",
        ),
        TestCase(
            query=QueryOption(
                parameter=dict(discipline=0, parameterCategory=5, parameterNumber=4),
                level_type="sfc",
                field_name="other_field_name",
            ),
            expected_grib_key_count=10,
            expected_field_name="other_field_name"
        )
    ]
)
def test_parameter_dict(grib2_gfs_basic_file_path, test_case):
    f = load_field_from_file(
        grib2_gfs_basic_file_path,
        **asdict(test_case.query),
    )
    assert f is not None
    assert f.name == test_case.expected_field_name
    assert f.attrs["GRIB_count"] == test_case.expected_grib_key_count
