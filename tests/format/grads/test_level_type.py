from reki.format.grads import load_field_from_file


def test_embedded_name(file_path, modelvar_file_path):
    test_cases = [
        ("t", "pl", 250, "pl", 250),
        ("u", "pl", 0.5, "pl", 0.5)
    ]

    for (parameter, level_type, level, expected_level_name, expected_level) in test_cases:
        field = load_field_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level,
        )
        assert field is not None
        assert field.name == parameter
        assert field.coords[expected_level_name] == expected_level

    test_cases = [
        ("u", "ml", 30, "ml", 30),
        ("w", "ml", 50, "ml", 50)
    ]

    for (parameter, level_type, level, expected_level_name, expected_level) in test_cases:
        field = load_field_from_file(
            modelvar_file_path,
            parameter=parameter,
            level_type=level_type,
            level=level,
        )
        assert field is not None
        assert field.name == parameter
        assert field.coords[expected_level_name] == expected_level


def test_index(file_path):
    test_cases = [
        ("tsoil", "index", 0, "level", 1000),
        ("tsoil", "index", 1, "level", 925),
        ("tsoil", "index", 2, "level", 850),
        ("tsoil", "index", 3, "level", 700)
    ]

    for (parameter, level_type, level, expected_level_name, expected_level) in test_cases:
        field = load_field_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level,
        )
        assert field is not None
        assert field.name == parameter
        assert field.coords[expected_level_name] == expected_level


def test_single(file_path):
    test_cases = [
        ("tcc", "single", None, "level", 0),
        ("t2mx", "single", None, "level", 0)
    ]

    for (parameter, level_type, level, expected_level_name, expected_level) in test_cases:
        field = load_field_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level,
        )
        assert field is not None
        assert field.name == parameter
        assert field.coords[expected_level_name] == expected_level


def test_none(file_path):
    test_cases = [
        ("tcc", None, None, "level", 0),
        ("t2mx", None, None, "level", 0)
    ]

    for (parameter, level_type, level, expected_level_name, expected_level) in test_cases:
        field = load_field_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level,
        )
        assert field is not None
        assert field.name == parameter
        assert field.coords[expected_level_name] == expected_level

