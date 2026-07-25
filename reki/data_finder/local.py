import datetime
from typing import Union, Optional, Iterable
from pathlib import Path

import pandas as pd

from reki.data_finder._config import (
    find_config, load_config, get_default_local_config_path,
)
from reki.data_finder._util import find_files, render_file_name
from reki.sources.local import LocalSource


def find_local_file(
        data_type: str,
        start_time: Union[str, pd.Timestamp, datetime.datetime],
        forecast_time: Union[str, pd.Timedelta] = "0",
        data_level: Optional[Union[str, Iterable]] = ("archive", "storage"),
        path_type: str = "local",
        data_class: str = "od",
        config_dir: Union[str, Path] = None,
        obs_time: Union[str, pd.Timestamp] = None,
        debug: bool = False,
        **kwargs,
) -> Optional[Path]:
    """
    Find local data path using config files in config dir.

    This is a compatibility wrapper: the resolution logic lives in
    ``reki.sources.local.LocalSource``. The signature and the return
    type (``Path`` or ``None`` when not found) are unchanged.

    Parameters
    ----------
    data_type
        data type, relative path of config file to `config_dir` without suffix.
        For example `grapes_gfs_gmf/grib2/orig` means using config file `{config_dir}/grapes_gfs_gmf/grib2/orig.yaml`.
    start_time
        start time of production. YYYYMMDDHH if str.
    forecast_time
        forecast time of production. A string (such as `3h`) will be parsed by ``pd.to_timedelta``.
    data_level
        data storage level, ["archive", "runtime", "storage", ... ], default is ``("archive", "storage")``.
    path_type
        path type, ["local", "storage", ...], for future usage.
    data_class
        data class, ``od`` means operational systems.
    config_dir
        config root directory. If None, use embedded config files in `conf` directory.
    obs_time
        time for observation data.
    debug
        show debug info.
    **kwargs
        other options needed by path template. All of them will be added into `query_vars`.

    Returns
    -------
    Path or None
        file path if found or None if not.

    Examples
    --------
    Find an existing orig grib2 file of CMA-GFS in CMA-PAI HPC.

    >>> find_local_file(
    ...     "cma_gfs_gmf/grib2/orig",
    ...     start_time="2023122000",
    ...     forecast_time="3h",
    ... )
    PosixPath('/g1/COMMONDATA/OPER/NWPC/GRAPES_GFS_GMF/Prod-grib/2023122000/ORIG/gmf.gra.2023122000003.grb2')

    Find a non-existing orig grib2 file of CMA-GFS.

    >>> find_local_file(
    ...     "cma_gfs_gmf/grib2/orig",
    ...     start_time="2020032100",
    ...     forecast_time="1h",
    ... )
    None

    """
    src = LocalSource(
        data_type,
        start_time,
        forecast_time,
        data_level=data_level,
        path_type=path_type,
        data_class=data_class,
        config_dir=config_dir,
        obs_time=obs_time,
        debug=debug,
        **kwargs,
    )
    return src.resolve_path()


def get_local_file_name(
        data_type: str,
        start_time: Union[str, pd.Timestamp, datetime.datetime],
        forecast_time: Union[str, pd.Timedelta] = pd.Timedelta(hours=1),
        data_class: str = "od",
        config_dir: Union[str, Path] = None,
        obs_time: Union[str, pd.Timestamp] = None,
        **kwargs,
) -> str:
    if config_dir is None:
        config_dir = get_default_local_config_path()

    config_file_path = find_config(config_dir, data_type, data_class)
    if config_file_path is None:
        raise ValueError(f"data type is not found: {data_type}")

    # if isinstance(forecast_time, str):
    #     forecast_time = pd.to_timedelta(forecast_time)

    if isinstance(start_time, str):
        start_time = pd.to_datetime(start_time, format="%Y%m%d%H")
    if isinstance(obs_time, str):
        obs_time = pd.to_datetime(obs_time)
    elif obs_time is None:
        obs_time = start_time

    config_content = load_config(config_file_path)
    file_name = render_file_name(
        config_content,
        start_time,
        forecast_time,
        obs_time=obs_time,
        **kwargs
    )
    return file_name


def find_local_files(
        data_type: str,
        start_time: Union[str, pd.Timestamp, datetime.datetime],
        forecast_time: Union[str, pd.Timedelta] = "0",
        data_level: Optional[Union[str, Iterable]] = ("archive", "storage"),
        path_type: str = "local",
        data_class: str = "od",
        config_dir: Union[str, Path] = None,
        glob: bool = True,
        **kwargs,
) -> Optional[Path]:
    if config_dir is None:
        config_dir = get_default_local_config_path()

    config_file_path = find_config(config_dir, data_type, data_class)
    if config_file_path is None:
        raise ValueError(f"data type is not found: {data_type}")

    if isinstance(forecast_time, str):
        forecast_time = pd.to_timedelta(forecast_time)
    if isinstance(start_time, str):
        start_time = pd.to_datetime(start_time, format="%Y%m%d%H")

    config_content = load_config(config_file_path)
    file_path = find_files(config_content, data_level, start_time, forecast_time, glob, **kwargs)
    return file_path
