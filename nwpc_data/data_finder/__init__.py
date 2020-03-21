import datetime
from pathlib import Path

import pandas as pd

from nwpc_data.data_finder._config import (
    find_config, load_config, get_default_local_config_path,
)
from nwpc_data.data_finder._util import find_file


def find_local_file(
        data_type: str,
        start_time: str or pd.Timestamp or datetime.datetime,
        forecast_time: str or pd.Timedelta,
        config_dir: str or Path or None = None,
        level: str = "archive",
):
    """Find local data path using config files in config dir.
    """
    if config_dir is None:
        config_dir = get_default_local_config_path()

    config_file_path = find_config(config_dir, data_type)
    if config_file_path is None:
        raise ValueError(f"data type is not found: {data_type}")

    if isinstance(forecast_time, str):
        forecast_time = pd.to_timedelta(forecast_time)
    if isinstance(start_time, str):
        start_time = pd.to_datetime(start_time, format="%Y%m%d%H")

    config = load_config(config_file_path)
    file_path = find_file(config, start_time, forecast_time, level)
    return file_path
