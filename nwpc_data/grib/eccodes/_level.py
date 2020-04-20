import typing


def _fix_level(
        level_type: str or typing.Dict or None,
        level_dim: str or None,
) -> typing.Tuple[str or dict, str]:
    if level_type is None:
        return level_type, level_dim

    if isinstance(level_type, dict):
        return level_type, level_dim

    if level_type == "pl":
        if level_dim is None:
            level_dim = level_type
        return {
            "typeOfFirstFixedSurface": 100,
        }, level_dim
    elif level_type == "sfc":
        if level_dim is None:
            level_dim = level_type
        return {
            "typeOfLevel": "surface"
        }, level_dim
    elif level_type == "ml":
        if level_dim is None:
            level_dim = level_type
        return {
            "typeOfFirstFixedSurface": 131,
            # "typeOfSecondFixedSurface": 255,
        }, level_dim
    return level_type, level_dim
