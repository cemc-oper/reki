from typing import Optional
from dataclasses import dataclass

import pandas as pd

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


@dataclass
class GribParameterKey:
    discipline: int
    category: int
    number: int
    first_level_type: Optional[int] = None
    first_level: Optional[float] = None
    second_level_type: Optional[int] = None
    second_level: Optional[float] = None
    stepType: Optional[str] = None


def check_value(expected_value, actual_value) -> bool:
    if expected_value is None or pd.isna(expected_value):
        return True
    if actual_value == "undef":
        return False
    return expected_value == actual_value


def find_wgrib2_name(param_key: GribParameterKey) -> Optional[str]:
    df = WGRIB2_SHORT_NAME_TABLE.query(
        f'discipline=={param_key.discipline} '
        f'& parameterCategory=={param_key.category} '
        f'& parameterNumber=={param_key.number}'
    )
    if not df.empty:
        return df.iloc[0]["short_name"]
    return None


def find_cemc_name(param_key: GribParameterKey) -> Optional[str]:
    param_df = CEMC_PARAM_TABLE.query(
        f'discipline=={param_key.discipline} '
        f'& category=={param_key.category} '
        f'& number=={param_key.number}'
    )
    param_df = param_df[~param_df['alias']]
    if param_df.empty:
        return None

    selected_rows = []
    for index, row in param_df.iterrows():
        if not check_value(row['stepType'], param_key.stepType):
            continue
        if not check_value(row['first_level_type'], param_key.first_level_type):
            continue
        if not check_value(row['second_level_type'], param_key.second_level_type):
            continue
        if not check_value(row['first_level'], param_key.first_level):
            continue
        if not check_value(row['second_level'], param_key.second_level):
            continue

        selected_rows.append(row)

    return selected_rows[-1]["name"]
