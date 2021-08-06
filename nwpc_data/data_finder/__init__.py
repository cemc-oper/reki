import datetime
from typing import Union, Optional, Iterable
from pathlib import Path

import pandas as pd

from nwpc_data.data_finder._config import (
    find_config, load_config, get_default_local_config_path,
)
from nwpc_data.data_finder._util import find_file, find_files


def find_local_file(
        data_type: str,
        start_time: Union[str, pd.Timestamp, datetime.datetime],
        forecast_time: Union[str, pd.Timedelta] = "0",
        data_level: Optional[Union[str, Iterable]] = ("archive", "storage"),
        path_type: str = "local",
        data_class: str = "od",
        config_dir: Union[str, Path] = None,
        obs_time: Union[str, pd.Timestamp] = None,
        **kwargs,
) -> Optional[Path]:
    """Find local data path using config files in config dir.

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
        data class, ``od`` means operation systems.
    config_dir
        config root directory. If None, use embedded config files in `conf` directory.
    obs_time
        time for observation data.
    **kwargs
        other options needed by path template. All of them will be added into `query_vars`.

    Returns
    -------
    Path or None
        file path if found or None if not.

    Examples
    --------
    Find an existing orig grib2 file of GRAPES GFS.

    >>> find_local_file(
    ...     "grapes_gfs_gmf/grib2/orig",
    ...     start_time="2020032100",
    ...     forecast_time="3h",
    ... )
    /g1/COMMONDATA/OPER/NWPC/GRAPES_GFS_GMF/Prod-grib/2020032021/ORIG/gmf.gra.2020032100003.grb2

    Find a non-existing orig grib2 file of GRAPES GFS.
    >>> find_local_file(
    ...     "grapes_gfs_gmf/grib2/orig",
    ...     start_time="2020032100",
    ...     forecast_time="1h",
    ... )
    None

    Find a grib2 file in storage for GRAPES MESO 3km.
    >>> find_local_file(
    ...     "grapes_meso_3km/grib2/orig",
    ...     start_time="2020032100",
    ...     forecast_time="1h",
    ...     data_level="storage",
    ... )
    /sstorage1/COMMONDATA/OPER/NWPC/GRAPES_MESO_3KM/Prod-grib/2020032021/ORIG/rmf.hgra.2020032100001.grb2

    Find a grib2 file in storage for GRAPES GEPS.
    >>> find_local_file(
    ...     "grapes_geps/grib2/orig",
    ...     start_time="2020032100",
    ...     forecast_time="3h",
    ...     data_level="storage",
    ...     number=1,
    ... )
    /sstorage1/COMMONDATA/OPER/NWPC/GRAPES_GEPS/Prod-grib/2020032100/grib2/gef.gra.001.2020032100003.grb2

    Find GRAPES TYM postvar ctl file in Windows mount storage.
    >>> find_local_file("grapes_tym/bin/postvar_ctl", start_time="2021080200", storage_base="Y:")
    WindowsPath('Y:/GRAPES_TYM/Fcst-main/2021080200/post.ctl_2021080200')

    """
    if config_dir is None:
        config_dir = get_default_local_config_path()

    config_file_path = find_config(config_dir, data_type, data_class)
    if config_file_path is None:
        raise ValueError(f"data type is not found: {data_type}")

    if isinstance(forecast_time, str):
        forecast_time = pd.to_timedelta(forecast_time)
    if isinstance(start_time, str):
        start_time = pd.to_datetime(start_time, format="%Y%m%d%H")
    if isinstance(obs_time, str):
        obs_time = pd.to_datetime(obs_time)

    config = load_config(config_file_path)
    file_path = find_file(
        config,
        data_level,
        start_time,
        forecast_time,
        obs_time=obs_time,
        **kwargs
    )
    return file_path


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

    config = load_config(config_file_path)
    file_path = find_files(config, data_level, start_time, forecast_time, glob, **kwargs)
    return file_path
