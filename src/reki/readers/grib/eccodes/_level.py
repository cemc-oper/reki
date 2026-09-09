from typing import Dict, List, Union, Optional, Tuple


def _fix_level(
        level_type: Optional[Union[str, Dict, List]],
        level_dim: Optional[str],
) -> Tuple[str or dict, str]:
    if level_type is None:
        return level_type, level_dim

    if isinstance(level_type, dict):
        return level_type, level_dim

    if isinstance(level_type, List):
        _, level_dim = _fix_level(level_type[0], level_dim)
        level_type = [_fix_level(cur_level, level_dim)[0] for cur_level in level_type]
        return level_type, level_dim

    if level_type == "pl":
        if level_dim is None:
            level_dim = level_type
        return {
            "typeOfFirstFixedSurface:int": 100,
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
            "typeOfFirstFixedSurface:int": 131,
            # "typeOfSecondFixedSurface": 255,
        }, level_dim
    return level_type, level_dim
