import datetime

import pandas as pd
import xarray as xr
import requests

from nwpc_data.grib.eccodes._bytes import create_message_from_bytes
from nwpc_data.grib.eccodes._xarray import create_xarray_array

from .transport import RawField, load_from_json


def load_message(
        system: str,
        stream: str,
        data_type: str,
        data_name: str,
        start_time: datetime.datetime or pd.Timestamp or str,
        forecast_time: pd.Timedelta or str,
        parameter: str,
        server: str,
        level_type: str = None,
        level: int = None,
        data_class: str = "od",
) -> int or None:
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
        start_time: datetime.datetime or pd.Timestamp or str,
        forecast_time: pd.Timedelta or str,
        parameter: str,
        server: str,
        level_type: str = None,
        level: int = None,
        data_class: str = "od",
) -> xr.DataArray or None:
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

    return create_xarray_array(message)
