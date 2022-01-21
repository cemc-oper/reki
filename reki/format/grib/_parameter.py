from typing import Union, Dict

from reki.format.grib.config import WGRIB2_SHORT_NAME_TABLE


def _convert_parameter(parameter: Union[str, Dict]) -> Union[str, Dict]:
    """
    Convert parameter short name into GRIB codes according to SHORT NAME TABLE.

    Parameters
    ----------
    parameter

    Returns
    -------

    """
    if isinstance(parameter, str):
        df = WGRIB2_SHORT_NAME_TABLE[WGRIB2_SHORT_NAME_TABLE["short_name"] == parameter]
        if not df.empty:
            return df.iloc[0].drop("short_name").to_dict()

    return parameter
