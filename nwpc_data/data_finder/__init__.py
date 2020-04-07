import datetime
import typing
from pathlib import Path

import pandas as pd

from nwpc_data.data_finder._config import (
    find_config, load_config, get_default_local_config_path,
)
from nwpc_data.data_finder._util import find_file


def find_local_file(
        data_type: str,
        start_time: str or pd.Timestamp or datetime.datetime,
        forecast_time: str or pd.Timedelta = "0",
        data_level: str or typing.Iterable or None = ("archive", "storage"),
        path_type: str = "local",
        data_class: str = "od",
        config_dir: str or Path or None = None,
        **kwargs,
) -> Path or None:
    """Find local data path using config files in config dir.

    Parameters
    ----------
    data_type: str
        data type, relative path of config file to `config_dir` without suffix.
        For example 'grapes_gfs_gmf/grib2/orig' means using config file `{config_dir}/grapes_gfs_gmf/grib2/orig.yaml`.
    start_time: str or pd.Timestamp or datetime.datetime
        start time of production. YYYYMMDDHH if str.
    forecast_time: str or pd.Timedelta
        forecast time of production. A string (such as `3h`) will be parsed by `pd.to_timedelta`.
    data_level: str or typing.Iterable or None
        data storage level, ["archive", "runtime", "storage", ... ], default is ("archive", "storage").
    path_type: str
        path type, ["local", "storage", ...], for future usage.
    data_class: str
        data class, ``od`` means operation systems, for future usage.
    config_dir: str or Path or None
        config root directory. If None, use embedded config files in `conf` directory.
    kwargs:
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

    config = load_config(config_file_path)
    file_path = find_file(config, data_level, start_time, forecast_time, **kwargs)
    return file_path
