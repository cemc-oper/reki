from dataclasses import dataclass, asdict
from typing import Union, Dict, Optional, List

import pytest
import eccodes
import numpy as np

from reki.format.grib.eccodes import load_message_from_file, load_messages_from_file


@dataclass
class QueryOption:
    parameter: Union[str, dict]
    level_type: Union[str, Dict]
    level: Optional[Union[float, Dict, List]]


@dataclass
class TestCase:
    query: QueryOption
    expected_keys: Optional[Dict] = None


def test_scalar(modelvar_file_path):
    test_cases = [
        TestCase(
            query=QueryOption(parameter="u", level_type={"typeOfFirstFixedSurface": 131}, level=10),
            expected_keys=dict(typeOfFirstFixedSurface=131, level=10)
        )
    ]
    for test_case in test_cases:
        message = load_message_from_file(
            modelvar_file_path,
            **asdict(test_case.query)
        )
        assert message is not None
        for key, expected_value in test_case.expected_keys.items():
            assert eccodes.codes_get(message, key, ktype=int) == expected_value

        eccodes.codes_release(message)
