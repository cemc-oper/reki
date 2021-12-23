import eccodes

from reki.format.grib.eccodes import load_message_from_file


def test_short_name(file_path):
    test_cases = [
        ("t", "pl", 850)
    ]
    for (parameter, level_type, level) in test_cases:
        message = load_message_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level,
        )
        assert message is not None
        eccodes.codes_release(message)


def test_numbers(file_path):
    """
    雷达组合反射率
    """
    test_cases = [
        ({
            "discipline": 0,
            "parameterCategory": 16,
            "parameterNumber": 225,
        }, "pl", 850)
    ]
    for (parameter, level_type, level) in test_cases:
        message = load_message_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level,
        )
        assert message is not None
        eccodes.codes_release(message)


def test_embedded_short_name(file_path):
    test_cases = [
        ("DEPR", "pl", 850),
        ({
            "discipline": 0,
            "parameterCategory": 0,
            "parameterNumber": 7,
        }, "pl", 850),
    ]

    messages = []
    for (parameter, level_type, level) in test_cases:
        message = load_message_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level,
        )
        assert message is not None
        messages.append(message)

    assert eccodes.codes_get(messages[0], "count") == eccodes.codes_get(messages[1], "count")

    for message in messages:
        eccodes.codes_release(message)
