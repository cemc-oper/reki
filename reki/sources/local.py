"""CMA HPC local path source (the ``data_finder`` kernel)."""

import datetime
from pathlib import Path
from typing import Optional, Union

import pandas as pd

from reki.core import Source
from reki.sources import get_source


class LocalSource(Source):
    """Resolve a data path on the CMA HPC file system.

    The path is resolved from YAML configs and Jinja2 templates (the
    former ``reki.data_finder.local`` logic). ``mutate()`` resolves the
    path and returns a ``FileSource`` for it.

    Parameters
    ----------
    data_type
        data type, relative path of the config file without suffix,
        e.g. ``"cma_gfs_gmf/grib2/orig"``.
    start_time
        start time of production. YYYYMMDDHH if str.
    forecast_time
        forecast time of production. A string (such as ``"3h"``) will
        be parsed by ``pd.to_timedelta``.
    **kwargs
        ``data_level`` / ``data_class`` / ``config_dir`` / ``obs_time``
        / ``debug`` and any extra variables used by the path template.
    """

    def __init__(
            self,
            data_type: str,
            start_time: Union[str, pd.Timestamp, datetime.datetime],
            forecast_time: Union[str, pd.Timedelta] = "0",
            **kwargs,
    ):
        super().__init__(**kwargs)
        self.data_type = data_type
        self.start_time = start_time
        self.forecast_time = forecast_time

    def mutate(self):
        path = self.resolve_path()
        if path is None:
            raise FileNotFoundError(f"Data not found: {self.data_type}")
        return get_source("file", path)

    def resolve_path(self) -> Optional[Path]:
        """Resolve the local data path, or return None if not found."""
        from reki.data_finder._config import (
            find_config,
            get_default_local_config_path,
            load_config,
        )
        from reki.data_finder._util import find_file

        kwargs = dict(self._kwargs)
        data_level = kwargs.pop("data_level", ("archive", "storage"))
        data_class = kwargs.pop("data_class", "od")
        config_dir = kwargs.pop("config_dir", None)
        obs_time = kwargs.pop("obs_time", None)
        debug = kwargs.pop("debug", False)
        kwargs.pop("path_type", None)  # reserved for future usage

        if config_dir is None:
            config_dir = get_default_local_config_path()

        config_file_path = find_config(config_dir, self.data_type, data_class)
        if config_file_path is None:
            raise ValueError(f"data type is not found: {self.data_type}")

        start_time = self.start_time
        forecast_time = self.forecast_time
        if isinstance(forecast_time, str):
            forecast_time = pd.to_timedelta(forecast_time)
        if isinstance(start_time, str):
            start_time = pd.to_datetime(start_time, format="%Y%m%d%H")
        if isinstance(obs_time, str):
            obs_time = pd.to_datetime(obs_time)
        elif obs_time is None:
            obs_time = start_time

        config_content = load_config(config_file_path)

        return find_file(
            config_content,
            data_level,
            start_time,
            forecast_time,
            obs_time=obs_time,
            debug=debug,
            **kwargs,
        )


source = LocalSource
