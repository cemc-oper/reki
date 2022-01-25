from dataclasses import dataclass, asdict
from typing import Dict, List, Union, Optional

from reki.format.grads import load_field_from_file


@dataclass
class QueryOption:
    parameter: str
    level_type: Optional[str]
    level: Optional[Union[int, float, List]]


@dataclass
class TestCase:
    query: QueryOption


def test_string(file_path):
    test_cases = [
        TestCase(query=QueryOption("t", "pl", 850)),
        TestCase(query=QueryOption("u", "pl", 0.1)),
        TestCase(query=QueryOption("lcc", None, None)),
    ]

    for test_case in test_cases:
        field = load_field_from_file(
            file_path,
            **asdict(test_case.query)
        )
        assert field is not None
        assert field.name == test_case.query.parameter
