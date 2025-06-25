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
    expected_grib_key_count: Optional[int] = None


@pytest.mark.parametrize(
    "test_case",
    [
        TestCase(
            query=QueryOption(parameter="t", level_type="pl", level=1.5, level_dim=None),
            expected_level_name="pl",
            expected_level=1.5,
            expected_grib_key_count=139,
        ),
        TestCase(
            query=QueryOption(parameter="t", level_type="pl", level=1.5, level_dim="pl"),
            expected_level_name="pl",
            expected_level=1.5,
            expected_grib_key_count=139,
        ),
        TestCase(
            query=QueryOption(parameter="t", level_type="pl", level=1.5, level_dim="isobaricInhPa"),
            expected_level_name="isobaricInhPa",
            expected_level=1.5,
            expected_grib_key_count=139,
        ),
        TestCase(
            query=QueryOption(parameter="t", level_type="pl", level=1.5, level_dim="isobaricInPa"),
            expected_level_name="isobaricInPa",
            expected_level=150.,
            expected_grib_key_count=139,

        ),
        TestCase(
            query=QueryOption(parameter="t", level_type="pl", level=1.5, level_dim="other_level_string"),
            expected_level_name="other_level_string",
            expected_level=1,
            expected_grib_key_count=139,
        )  # TODO: use float point?
    ]
)
def test_pl(grib2_gfs_basic_file_path, test_case):
    field = load_field_from_file(
        grib2_gfs_basic_file_path,
        **asdict(test_case.query)
    )
    assert field is not None
    assert field.coords[test_case.expected_level_name].values == test_case.expected_level
    assert field.attrs["GRIB_count"] == test_case.expected_grib_key_count


@pytest.mark.parametrize(
    "test_case",
    [
        TestCase(
            query=QueryOption(parameter="t", level_type="sfc", level=None, level_dim=None),
            expected_level_name="sfc",
            expected_level=0,
            expected_grib_key_count=5,
        ),
        TestCase(
            query=QueryOption(parameter="t", level_type="sfc", level=None, level_dim="sfc"),
            expected_level_name="sfc",
            expected_level=0,
            expected_grib_key_count=5,
        ),
        TestCase(
            query=QueryOption(parameter="t", level_type="sfc", level=None, level_dim="other_level_string"),
            expected_level_name="other_level_string",
            expected_level=0,
            expected_grib_key_count=5,
        ),
    ]
)
def test_sfc(grib2_gfs_basic_file_path, test_case):
    field = load_field_from_file(
        grib2_gfs_basic_file_path,
        **asdict(test_case.query)
    )
    assert field is not None
    assert field.coords[test_case.expected_level_name].values == test_case.expected_level
    assert field.attrs["GRIB_count"] == test_case.expected_grib_key_count


@pytest.mark.parametrize(
    "test_case",
    [
        TestCase(
            query=QueryOption(parameter="gh", level_type="isobaricInhPa", level=10, level_dim=None),
            expected_level_name="isobaricInhPa",
            expected_level=10,
            expected_grib_key_count=93,
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type="isobaricInhPa", level=10, level_dim="other_level_string"),
            expected_level_name="other_level_string",
            expected_level=10,
            expected_grib_key_count=93,
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type="isobaricInPa", level=50, level_dim=None),
            expected_level_name="isobaricInPa",
            expected_level=50,
            expected_grib_key_count=101,
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type="isobaricInPa", level=50, level_dim="other_level_string"),
            expected_level_name="other_level_string",
            expected_level=50,
            expected_grib_key_count=101,
        ),
        TestCase(
            query=QueryOption(parameter="sulwrf", level_type="surface", level=None, level_dim=None),
            expected_level_name="surface",
            expected_level=0,
            expected_grib_key_count=10,
        ),
        TestCase(
            query=QueryOption(parameter="tmax", level_type="heightAboveGround", level=2, level_dim=None),
            expected_level_name="heightAboveGround",
            expected_level=2,
            expected_grib_key_count=40,
        ),
        TestCase(
            query=QueryOption(parameter="prmsl", level_type="meanSea", level=None, level_dim=None),
            expected_level_name="meanSea",
            expected_level=0,
            expected_grib_key_count=45,
        ),
        TestCase(
            query=QueryOption(parameter="q", level_type="depthBelowLandLayer", level={"first_level": 0.1, "second_level": 0.4}, level_dim=None),
            expected_level_name="depthBelowLandLayer",
            expected_level=0,
            expected_grib_key_count=469,
        ),
        TestCase(
            query=QueryOption(parameter="t", level_type="depthBelowLandLayer", level={"first_level": 1, "second_level": 2}, level_dim=None),
            expected_level_name="depthBelowLandLayer",
            expected_level=1,
            expected_grib_key_count=467,
        ),
        TestCase(
            query=QueryOption(parameter="vwsh", level_type="heightAboveGroundLayer", level={"first_level": 1000, "second_level": 0}, level_dim=None),
            expected_level_name="heightAboveGroundLayer",
            expected_level=1000,
            expected_grib_key_count=781,
        ),
    ]
)
def test_type_of_level(grib2_gfs_basic_file_path, test_case):
    field = load_field_from_file(
        grib2_gfs_basic_file_path,
        **asdict(test_case.query),
    )
    assert field is not None
    assert field.coords[test_case.expected_level_name].values == test_case.expected_level
    assert field.attrs["GRIB_count"] == test_case.expected_grib_key_count


@pytest.mark.parametrize(
    "test_case",
    [
        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level=10, level_dim=None),
            expected_level_name="isobaricInhPa",
            expected_level=10,
            expected_grib_key_count=93,
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level=10, level_dim="pl"),
            expected_level_name="pl",
            expected_level=10,
            expected_grib_key_count=93,
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level=10, level_dim="isobaricInhPa"),
            expected_level_name="isobaricInhPa",
            expected_level=10,
            expected_grib_key_count=93,
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level=10, level_dim="isobaricInPa"),
            expected_level_name="isobaricInPa",
            expected_level=1000,
            expected_grib_key_count=93,
        ),

        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level={"first_level": 150}, level_dim=None),
            expected_level_name="isobaricInhPa",
            expected_level=1,
            expected_grib_key_count=99,
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level={"first_level": 150}, level_dim="pl"),
            expected_level_name="pl",
            expected_level=1.5,
            expected_grib_key_count=99,
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level={"first_level": 150}, level_dim="isobaricInhPa"),
            expected_level_name="isobaricInhPa",
            expected_level=1.5,
            expected_grib_key_count=99,
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level={"first_level": 150}, level_dim="isobaricInPa"),
            expected_level_name="isobaricInPa",
            expected_level=150,
            expected_grib_key_count=99,
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level={"first_level": 150}, level_dim="other_level_string"),
            expected_level_name="other_level_string",
            expected_level=1,
            expected_grib_key_count=99,
        ),

        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level={"first_level": 50}, level_dim=None),
            expected_level_name="isobaricInPa",
            expected_level=50,
            expected_grib_key_count=101,
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level={"first_level": 50}, level_dim="pl"),
            expected_level_name="pl",
            expected_level=0.5,
            expected_grib_key_count=101,
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level={"first_level": 50}, level_dim="isobaricInhPa"),
            expected_level_name="isobaricInhPa",
            expected_level=0.5,
            expected_grib_key_count=101,
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level={"first_level": 50}, level_dim="isobaricInPa"),
            expected_level_name="isobaricInPa",
            expected_level=50,
            expected_grib_key_count=101,
        ),
        TestCase(
            query=QueryOption(parameter="gh", level_type={"typeOfFirstFixedSurface": "pl"}, level={"first_level": 50}, level_dim="other_level_string"),
            expected_level_name="other_level_string",
            expected_level=50,
            expected_grib_key_count=101,
        ),
    ]
)
def test_grib_key_for_pl(grib2_gfs_basic_file_path, test_case):
    field = load_field_from_file(
        grib2_gfs_basic_file_path,
        **asdict(test_case.query)
    )
    assert field is not None
    assert field.coords[test_case.expected_level_name].values == test_case.expected_level
    assert field.attrs["GRIB_count"] == test_case.expected_grib_key_count
