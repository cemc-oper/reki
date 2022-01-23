from dataclasses import dataclass, asdict
from typing import Union, Dict, Optional, List

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


def test_embedded_level_name(file_path, modelvar_file_path):
    """
    embedded level type:

    * pl
    * surface
    * ml
    """
    test_cases = [
        TestCase(query=QueryOption(parameter="t", level_type="pl", level=850)),
        TestCase(query=QueryOption(parameter="t", level_type="sfc", level=None)),
    ]
    for test_case in test_cases:
        message = load_message_from_file(
            file_path,
            **asdict(test_case.query)
        )
        assert message is not None
        eccodes.codes_release(message)

    test_cases = [
        TestCase(query=QueryOption(parameter="u", level_type="ml", level=10))
    ]
    for test_case in test_cases:
        message = load_message_from_file(
            modelvar_file_path,
            **asdict(test_case.query)
        )
        assert message is not None
        eccodes.codes_release(message)


def test_type_of_level(file_path):
    test_cases = [
        TestCase(query=QueryOption(parameter="t", level_type="isobaricInhPa", level=850)),
        TestCase(query=QueryOption(parameter="t", level_type="isobaricInPa", level=50)),
        TestCase(query=QueryOption(parameter="asnow", level_type="surface", level=None)),
        TestCase(query=QueryOption(parameter="tmax", level_type="heightAboveGround", level=2)),
        TestCase(query=QueryOption(parameter="lcc", level_type="nominalTop", level=None)),
        TestCase(query=QueryOption(parameter="tciwv", level_type="atmosphere", level=None)),
        TestCase(query=QueryOption(parameter="prmsl", level_type="meanSea", level=None)),
        TestCase(query=QueryOption(parameter="t", level_type="depthBelowLandLayer", level={"first_level": 0, "second_level": 0.1}))
    ]

    for test_case in test_cases:
        message = load_message_from_file(
            file_path,
            **asdict(test_case.query)
        )
        assert message is not None
        eccodes.codes_release(message)


def test_grib_key(modelvar_file_path):
    test_cases = [
        TestCase(query=QueryOption(parameter="u", level_type={"typeOfFirstFixedSurface": 131}, level=10))
    ]
    for test_case in test_cases:
        message = load_message_from_file(
            modelvar_file_path,
            **asdict(test_case.query)
        )
        assert message is not None
        eccodes.codes_release(message)
