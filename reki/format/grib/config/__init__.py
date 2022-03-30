from typing import Optional

from .wgrib2_short_name import WGRIB2_SHORT_NAME_TABLE
from .cemc_param_table import CEMC_PARAM_TABLE


def find_short_name(discipline: int, category: int, number: int) -> Optional[str]:
    """
    Get parameter's short name from WGRIB2 and CEMC param table.

    Parameters
    ----------
    discipline
        GRIB key discipline
    category
        GRIB key parameterCategory
    number
        GRIB key parameterNumber

    Returns
    -------
    Optional[str]
        short name if found, or None if not.
    """
    df = WGRIB2_SHORT_NAME_TABLE.query(
        f'discipline=={discipline} & parameterCategory=={category} & parameterNumber=={number}'
    )
    if not df.empty:
        return df.iloc[0]["short_name"]

    param_df = CEMC_PARAM_TABLE.query(
        f'discipline=={discipline} & category=={category} & number=={number}'
    )
    if not param_df.empty:
        return param_df.iloc[0]["name"]

    return None
