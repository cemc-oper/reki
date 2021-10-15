import datetime
from typing import Union, Optional

import pandas as pd
import xarray as xr
import requests

from reki.format.grib.eccodes.bytes import create_message_from_bytes
from reki.format.grib.eccodes._xarray import create_data_array_from_message

from .transport import RawField, load_from_json


def load_message(
        system: str,
        stream: str,
        data_type: str,
        data_name: str,
        start_time: Union[datetime.datetime, pd.Timestamp, str],
        forecast_time: Union[pd.Timedelta, str],
        parameter: str,
        server: str,
        level_type: Optional[str] = None,
        level: Optional[int] = None,
        data_class: str = "od",
) -> Optional[int]:
    url = f"http://{server}/api/v1/gdata/fetch/field"

    if not isinstance(start_time, str):
        start_time = start_time.strftime("%Y-%m-%d %H:%M:%S")

    if not isinstance(start_time, str):
        forecast_time = forecast_time.isoformat()

    result = requests.post(url, json={
        "query": {
            "class": data_class,
            "system": system,
            "stream": stream,
            "type": data_type,
            "name": data_name,
            "start_time": start_time,
            "forecast_time": forecast_time,
            "parameter": parameter,
            "level_type": level_type,
            "level": level,
        }
    })

    if result.json()["status"] != "complete":
        return None

    raw_field = result.json()["raw_field"]
    message = load_from_json(raw_field, RawField)

    raw_bytes = message.raw_bytes

    grib_message = create_message_from_bytes(raw_bytes)
    return grib_message


def load_field(
        system: str,
        stream: str,
        data_type: str,
        data_name: str,
        start_time: Union[datetime.datetime, pd.Timestamp, str],
        forecast_time: Union[pd.Timedelta, str],
        parameter: str,
        server: str,
        level_type: str = None,
        level: int = None,
        data_class: str = "od",
) -> Optional[xr.DataArray]:
    message = load_message(
        data_class=data_class,
        system=system,
        stream=stream,
        data_type=data_type,
        data_name=data_name,
        start_time=start_time,
        forecast_time=forecast_time,
        parameter=parameter,
        level_type=level_type,
        level=level,
        server=server,
    )
    if message is None:
        return None

    return create_data_array_from_message(message)
