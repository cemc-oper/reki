from typing import Optional, Union, Dict


def fix_level_type(
        level_type: Optional[Union[str, Dict]],
        engine: str = "eccodes",
) -> Optional[Union[str, Dict]]:
    """
    Convert level type into GRIB keys with values.

    Notes
    -----
    ``typeOfFirstFixedSurface`` is not working in cfgrib engine.

    """
    if level_type is None:
        return level_type
    if isinstance(level_type, dict):
        return level_type
    if level_type == "pl":
        if engine == "cfgrib":
            return {
                "typeOfLevel": "isobaricInhPa"
            }
        else:
            return {
                "typeOfFirstFixedSurface": 100,
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
    return level_type
