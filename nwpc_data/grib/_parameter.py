from typing import Union, Dict

from nwpc_data.grib.config.short_name import SHORT_NAME_TABLE


def _convert_parameter(parameter: Union[str, Dict]) -> Union[str, Dict]:
    if isinstance(parameter, str):
        df = SHORT_NAME_TABLE[SHORT_NAME_TABLE["short_name"] == parameter]
        if df.empty:
            return parameter
        else:
            return df.iloc[0].drop("short_name").to_dict()
    else:
        return parameter
