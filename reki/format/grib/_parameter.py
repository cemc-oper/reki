from typing import Union, Dict

from reki.format.grib.config import WGRIB2_SHORT_NAME_TABLE, CEMC_PARAM_TABLE


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

        param_df = CEMC_PARAM_TABLE[CEMC_PARAM_TABLE["name"] == parameter]
        if not param_df.empty:
            row = param_df.iloc[0]
            return dict(
                discipline=float(row["discipline"]),
                parameterCategory=float(row["category"]),
                parameterNumber=float(row["number"]),
            )

    return parameter
