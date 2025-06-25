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
        TestCase(
            query=QueryOption(parameter="t", level_type="pl", level=850),
            expected_keys={"count": 109},
        ),
    ]
)
def test_short_name(grib2_gfs_basic_file_path, test_case):
    message = load_message_from_file(
        grib2_gfs_basic_file_path,
        **asdict(test_case.query)
    )
    assert message is not None
    for key, expected_value in test_case.expected_keys.items():
        assert eccodes.codes_get(message, key) == expected_value
    eccodes.codes_release(message)


@pytest.mark.parametrize(
    "test_case",
    [
        TestCase(
            query=QueryOption(parameter={
                "discipline": 0,
                "parameterCategory": 16,
                "parameterNumber": 225,
            }, level_type="pl", level=850),
            expected_keys={"count": 789},
        )
    ]
)
def test_numbers(grib2_gfs_basic_file_path, test_case):
    """
    雷达组合反射率
    """
    message = load_message_from_file(
        grib2_gfs_basic_file_path,
        **asdict(test_case.query)
    )
    assert message is not None
    eccodes.codes_release(message)


def test_embedded_short_name(grib2_gfs_basic_file_path):
    test_cases = [
        TestCase(
            query=QueryOption("DEPR", "pl", 850),
            expected_keys={"count": 719}
        ),
        TestCase(
            query=QueryOption({
                "discipline": 0,
                "parameterCategory": 0,
                "parameterNumber": 7,
            }, "pl", 850),
            expected_keys={"count": 719}
        ),
    ]

    messages = []
    for test_case in test_cases:
        message = load_message_from_file(
            grib2_gfs_basic_file_path,
            **asdict(test_case.query)
        )
        assert message is not None
        for key, expected_value in test_case.expected_keys.items():
            assert eccodes.codes_get(message, key) == expected_value
        messages.append(message)

    assert eccodes.codes_get(messages[0], "count") == eccodes.codes_get(messages[1], "count")

    for message in messages:
        eccodes.codes_release(message)
