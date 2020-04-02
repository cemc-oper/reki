import typing


def fix_level_type(level_type: str or typing.Dict or None) -> str or typing.Dict:
    """

    Notes
    -----
    ``typeOfFirstFixedSurface`` is not working in cfgrib engine.

    """
    if level_type is None:
        return level_type
    if isinstance(level_type, dict):
        return level_type
    if level_type == "pl":
        return {
            "typeOfLevel": "isobaricInhPa"
        }
    elif level_type == "sfc":
        return {
            "typeOfLevel": "sfc"
        }
    elif level_type == "ml":
        return {
            "typeOfFirstFixedSurface": 131,
            # "typeOfSecondFixedSurface": 255,
        }
