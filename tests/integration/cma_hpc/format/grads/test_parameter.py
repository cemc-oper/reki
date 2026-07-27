from dataclasses import dataclass, asdict
from typing import List, Union, Optional

from reki.format.grads import load_field_from_file


@dataclass
class QueryOption:
    parameter: str
    level_type: Optional[str]
    level: Optional[Union[int, float, List]]


@dataclass
class TestCase:
    query: QueryOption


def test_string(file_path, forecast_time):
    test_cases = [
        TestCase(query=QueryOption("t", "pl", 850)),
        TestCase(query=QueryOption("u", "pl", 10)),
        TestCase(query=QueryOption("cr", None, None)),
    ]

    for test_case in test_cases:
        field = load_field_from_file(
            file_path,
            forecast_time=forecast_time,
            **asdict(test_case.query)
        )
        assert field is not None
        assert field.name == test_case.query.parameter
