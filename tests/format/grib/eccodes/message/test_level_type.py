import eccodes

from reki.format.grib.eccodes import load_message_from_file


def test_embedded_level_name(file_path, modelvar_file_path):
    """
    embedded level type:

    * pl
    * surface
    * ml
    """
    test_cases = [
        ("t", "pl", 850),
        ("t", "sfc", None),
    ]
    for (parameter, level_type, level) in test_cases:
        message = load_message_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level
        )
        assert message is not None
        eccodes.codes_release(message)

    test_cases = [
        ("u", "ml", 10)
    ]
    for (parameter, level_type, level) in test_cases:
        message = load_message_from_file(
            modelvar_file_path,
            parameter=parameter,
            level_type=level_type,
            level=level
        )
        assert message is not None
        eccodes.codes_release(message)


def test_type_of_level(file_path):
    # (parameter, level_type, level)
    test_cases = [
        ("t", "isobaricInhPa", 850),
        ("t", "isobaricInPa", 50),
        ("asnow", "surface", None),
        ("tmax", "heightAboveGround", 2),
        ("lcc", "nominalTop", None),
        ("tciwv", "atmosphere", None),
        ("prmsl", "meanSea", None),
        ("t", "depthBelowLandLayer", {"first_level": 0, "second_level": 0.1})
    ]

    for (parameter, level_type, level) in test_cases:
        message = load_message_from_file(
            file_path,
            parameter=parameter,
            level_type=level_type,
            level=level
        )
        assert message is not None
        eccodes.codes_release(message)


def test_grib_key(modelvar_file_path):
    test_cases = [
        ("u", {"typeOfFirstFixedSurface": 131}, 10)
    ]
    for (parameter, level_type, level) in test_cases:
        message = load_message_from_file(
            modelvar_file_path,
            parameter=parameter,
            level_type=level_type,
            level=level
        )
        assert message is not None
        eccodes.codes_release(message)
