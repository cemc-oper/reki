from dataclasses import dataclass, asdict
from typing import Union, Dict, Optional, List

import pytest
import eccodes

from reki.format.grib.eccodes import load_message_from_file


@dataclass
class QueryOption:
    parameter: Union[str, dict]
    level_type: Union[str, Dict]
    level: Optional[Union[float, Dict, List]]


@dataclass
class TestCase:
    query: QueryOption
    expected_keys: Optional[Dict] = None


@pytest.mark.parametrize(
    "test_case",
    [
    TestCase(query=QueryOption(parameter="t", level_type="pl", level=850)),
        TestCase(query=QueryOption(parameter="t", level_type="sfc", level=None)),
    ]
)
def test_embedded_level_name(grib2_gfs_basic_file_path, test_case):
    """
    embedded level type:

    * pl
    * surface
    * ml
    """
    message = load_message_from_file(
        grib2_gfs_basic_file_path,
        **asdict(test_case.query)
    )
    assert message is not None
    eccodes.codes_release(message)


@pytest.mark.parametrize(
    "test_case",
    [
        TestCase(query=QueryOption(parameter="t", level_type="isobaricInhPa", level=850)),
        TestCase(query=QueryOption(parameter="t", level_type="isobaricInPa", level=50)),
        TestCase(query=QueryOption(parameter="acpcp", level_type="surface", level=None)),
        TestCase(query=QueryOption(parameter="tmax", level_type="heightAboveGround", level=2)),
        TestCase(query=QueryOption(parameter="lcc", level_type="entireAtmosphere", level=None)),
        TestCase(query=QueryOption(parameter="sulwrf", level_type="surface", level=None)),
        TestCase(query=QueryOption(parameter="pwat", level_type="atmosphere", level=None)),
        TestCase(query=QueryOption(parameter="prmsl", level_type="meanSea", level=None)),
        TestCase(query=QueryOption(parameter="t", level_type="depthBelowLandLayer",
                                   level={"first_level": 0, "second_level": 0.1})),
        TestCase(query=QueryOption(parameter="vwsh", level_type="heightAboveGroundLayer", level=1000))
    ]
)
def test_type_of_level(grib2_gfs_basic_file_path, test_case):
    message = load_message_from_file(
        grib2_gfs_basic_file_path,
        **asdict(test_case.query)
    )
    assert message is not None
    eccodes.codes_release(message)
