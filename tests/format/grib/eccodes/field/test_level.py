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
    expected_grib_key_count: Optional[Union[int, list]] = None
    expected_level_name: Optional[str] = None
    expected_level: Optional[float] = None


@pytest.mark.parametrize(
    "test_case",
    [
        TestCase(
            query=QueryOption(parameter="t", level_type="pl", level=1.5),
            expected_grib_key_count=139,
            expected_level_name="pl",
            expected_level=1.5,
        ),
        TestCase(
            query=QueryOption(parameter="t", level_type="isobaricInhPa", level=850),
            expected_grib_key_count=109,
            expected_level_name="isobaricInhPa",
            expected_level=850
        ),
        TestCase(
            query=QueryOption(parameter="TMAX", level_type="heightAboveGround", level=2),
            expected_grib_key_count=40,
            expected_level_name="heightAboveGround",
            expected_level=2
        ),
    ]
)
def test_scalar(grib2_gfs_basic_file_path, test_case):
    field = load_field_from_file(
        grib2_gfs_basic_file_path,
        **asdict(test_case.query)
    )
    assert field is not None
    assert field.coords[test_case.expected_level_name] == test_case.expected_level
    assert field.attrs["GRIB_count"] == test_case.expected_grib_key_count


@pytest.mark.parametrize(
    "test_case",
    [
        TestCase(
            QueryOption(
                parameter="vwsh",
                level_type="heightAboveGroundLayer",
                level=dict(first_level=1000, second_level=0)
            ),
            expected_grib_key_count=781,
        ),
        TestCase(
            QueryOption(
                parameter="t",
                level_type="depthBelowLandLayer",
                level=dict(first_level=0.1, second_level=0.4)
            ),
            expected_grib_key_count=465,
        )
    ]
)
def test_dict(grib2_gfs_basic_file_path, test_case):
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
            query=QueryOption(parameter="t", level_type="pl", level=[850, 925, 1000]),
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type="isobaricInhPa", level=[850, 925, 1000]),
        )
    ]
)
def test_multi_levels(grib2_gfs_basic_file_path, test_case):
    field = load_field_from_file(
        grib2_gfs_basic_file_path,
        **asdict(test_case.query)
    )
    assert field is not None
    assert np.array_equal(
        np.sort(field.coords[test_case.query.level_type].values),
        np.sort(test_case.query.level).astype(float)
    )


@pytest.fixture
def pl_levels():
    return [
        1000,
        975,
        950,
        925,
        900,
        850,
        800,
        750,
        700,
        650,
        600,
        550,
        500,
        450,
        400,
        350,
        300,
        275,
        250,
        225,
        200,
        175,
        150,
        125,
        100,
        70,
        50,
        30,
        20,
        10,
        7,
        5,
        4,
        3,
        2,
        1.5,
        1,
        0.5,
        0.2,
        0.1
    ]


@pytest.mark.parametrize(
    "test_case",
    [
        TestCase(
            query=QueryOption(
                parameter="t",
                level_type="pl",
                level="all"
            ),
            expected_level_name="pl",
        ),
    ]
)
def test_all_levels(grib2_gfs_basic_file_path, pl_levels, test_case):
    field = load_field_from_file(
        grib2_gfs_basic_file_path,
        **asdict(test_case.query)
    )
    assert field is not None
    assert np.array_equal(
        np.sort(field.coords[test_case.expected_level_name].values),
        np.sort(pl_levels).astype(float)
    )


@pytest.mark.parametrize(
    "test_case",
    [
        TestCase(
            query=QueryOption(parameter="t", level_type="pl", level=None),
            expected_grib_key_count=104,
            expected_level_name="pl",
            expected_level=1000,
        ),
        TestCase(
            query=QueryOption(parameter="vwsh", level_type="heightAboveGroundLayer", level=None),
            expected_grib_key_count=781,
            expected_level_name="heightAboveGroundLayer",
            expected_level=1000,
        )
    ]
)
def test_none_level(grib2_gfs_basic_file_path, test_case):
    field = load_field_from_file(
        grib2_gfs_basic_file_path,
        **asdict(test_case.query)
    )
    assert field is not None
    assert field.coords[test_case.expected_level_name].values == test_case.expected_level
    assert field.attrs["GRIB_count"] == test_case.expected_grib_key_count