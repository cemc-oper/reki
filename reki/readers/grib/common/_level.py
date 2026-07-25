from typing import Optional, Union, Dict, Literal


def fix_level_type(
        level_type: Optional[Union[str, Dict]],
        engine: Literal["eccodes", "cfgrib"] = "eccodes",
) -> Optional[Union[str, Dict]]:
    """
    Convert level type into dict of GRIB key(s).

    Convert some string level to GRIB key(s).

        - pl
        - ml
        - sfc

    If level_type is Dict, or not one of above strings, just return level_type value.

    Notes
    -----
    ``typeOfFirstFixedSurface`` is not working in cfgrib engine.

    Parameters
    ----------
    level_type
    engine
        load engine:

        - cfgrib: use cfgrib to load message
        - eccodes: use eccodes to load message

    """
    if level_type is None:
        return level_type
    if isinstance(level_type, Dict):
        return level_type
    if level_type == "pl":
        if engine == "cfgrib":
            return {
                "typeOfLevel": "isobaricInhPa"
            }
        else:
            return {
                "typeOfFirstFixedSurface:int": 100,
            }
    elif level_type == "sfc":
        return {
            "typeOfLevel": "sfc"
        }
    elif level_type == "ml":
        return {
            "typeOfFirstFixedSurface:int": 131,
            # "typeOfSecondFixedSurface": 255,
        }
    return level_type
