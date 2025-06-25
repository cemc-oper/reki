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
    expected_grib_key_count: int


@pytest.mark.parametrize(
    "test_case",
    [
        TestCase(
            query=QueryOption(parameter="t", level_type="pl", level=850),
            expected_grib_key_count=109,
        ),
        TestCase(
            query=QueryOption(parameter="t", level_type="sfc", level=None),
            expected_grib_key_count=5,
        ),
    ]
)
def test_embedded_level_name(grib2_gfs_basic_file_path, test_case):
    """
    embedded level type:

    * pl
    * surface
    * ml
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
            query=QueryOption(parameter="t", level_type="isobaricInhPa", level=850),
            expected_grib_key_count=109,
        ),
        TestCase(
            query=QueryOption(parameter="t", level_type="isobaricInPa", level=50),
            expected_grib_key_count=141
        ),
        TestCase(
            query=QueryOption(parameter="acpcp", level_type="surface", level=None),
            expected_grib_key_count=1,
        ),
        TestCase(
            query=QueryOption(parameter="tmax", level_type="heightAboveGround", level=2),
            expected_grib_key_count=40,
        ),
        TestCase(
            query=QueryOption(parameter="lcc", level_type="entireAtmosphere", level=None),
            expected_grib_key_count=29,
        ),
        TestCase(
            query=QueryOption(parameter="sulwrf", level_type="surface", level=None),
            expected_grib_key_count=10,
        ),
        TestCase(
            query=QueryOption(parameter="pwat", level_type="atmosphere", level=None),
            expected_grib_key_count=820,
        ),
        TestCase(
            query=QueryOption(parameter="prmsl", level_type="meanSea", level=None),
            expected_grib_key_count=45,
        ),
        TestCase(
            query=QueryOption(parameter="t", level_type="depthBelowLandLayer", level={"first_level": 0, "second_level": 0.1}),
            expected_grib_key_count=464,
        ),
        TestCase(
            query=QueryOption(parameter="vwsh", level_type="heightAboveGroundLayer", level=1000),
            expected_grib_key_count=781,
        )
    ]
)
def test_type_of_level(grib2_gfs_basic_file_path, test_case):
    field = load_field_from_file(
        grib2_gfs_basic_file_path,
         **asdict(test_case.query)
    )
    assert field is not None
    assert field.attrs["GRIB_count"] == test_case.expected_grib_key_count
