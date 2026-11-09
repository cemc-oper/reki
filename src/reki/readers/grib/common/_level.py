from typing import Optional, Union, Dict, Literal


def fix_level_type(
        level_type: Optional[Union[str, Dict]],
        engine: Literal["eccodes"] = "eccodes",
) -> Optional[Union[str, Dict]]:
    """Translate native level aliases for the supported ecCodes engine."""
    from reki._legacy import check_engine
    check_engine(engine)
    if level_type is None or isinstance(level_type, dict):
        return level_type
    return {"pl": {"typeOfFirstFixedSurface:int": 100},
            "sfc": {"typeOfLevel": "surface"},
            "ml": {"typeOfFirstFixedSurface:int": 131}}.get(level_type, level_type)
