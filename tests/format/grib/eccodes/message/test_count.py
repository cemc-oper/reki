import eccodes

from reki.format.grib.eccodes import load_message_from_file


def test_count(file_path):
    test_cases = [
        (10, dict(count=10)),
        (20, dict(count=20)),
    ]

    for (count, expected_keys) in test_cases:
        message = load_message_from_file(
            file_path,
            count=count
        )
        assert message is not None
        for key, expected_value in expected_keys.items():
            assert eccodes.codes_get(message, key, ktype=int) == expected_value

        eccodes.codes_release(message)
