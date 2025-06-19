from dataclasses import dataclass, asdict
from typing import Dict

import pytest
import eccodes

from reki.format.grib.eccodes import load_message_from_file


@dataclass
class QueryOption:
    count: int


@dataclass
class TestCase:
    query: QueryOption
    expected_keys: Dict


@pytest.mark.parametrize(
    "test_case",
    [
        TestCase(query=QueryOption(count=10), expected_keys=dict(count=10)),
        TestCase(query=QueryOption(count=20), expected_keys=dict(count=20)),
    ]
)
def test_count(grib2_gfs_basic_file_path, test_case):
    message = load_message_from_file(
        grib2_gfs_basic_file_path,
        **asdict(test_case.query)
    )
    assert message is not None
    for key, expected_value in test_case.expected_keys.items():
        assert eccodes.codes_get(message, key, ktype=int) == expected_value

    eccodes.codes_release(message)
