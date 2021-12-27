

from reki.format.grads import load_field_from_file


def test_string(file_path):
    test_cases = [
        ("t", "pl", 850),
        ("u", "pl", 0.1),
        ("lcc", None, None),
    ]

    for (parameter, level_type, level) in test_cases:
        field = load_field_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level,
        )
        assert field is not None
        assert field.name == parameter
