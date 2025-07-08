from pathlib import Path

import pytest
import pandas as pd


@pytest.fixture
def cma_gfs_system_name() -> str:
    return "cma_gfs_gmf"


@pytest.fixture
def last_two_day() -> pd.Timestamp:
    current = pd.Timestamp.now().floor(freq="D")
    last_two_day = current - pd.Timedelta(days=2)
    return last_two_day


@pytest.fixture
def forecast_time_24h() -> pd.Timedelta:
    return pd.to_timedelta("24h")


@pytest.fixture
def forecast_time_12h() -> pd.Timedelta:
    return pd.to_timedelta("12h")


@pytest.fixture
def cma_gfs_grib2_orig_dir():
    return "/g3/COMMONDATA/OPER/CEMC/GFS_GMF/Prod-grib/{start_time_label}/ORIG"

@pytest.fixture
def cma_gfs_grib2_modelvar_dir():
    return "/g3/COMMONDATA/OPER/CEMC/GFS_GMF/Prod-grib/{start_time_label}/MODELVAR"


@pytest.fixture
def meso_gfs_grib2_orig_dir():
    return "/g3/COMMONDATA/OPER/CEMC/MESO_1KM/Prod-grib/{start_time_label}/ORIG"


@pytest.fixture
def meso_grib2_orig_file_path(meso_gfs_grib2_orig_dir, last_two_day, forecast_time_24h):
    start_time_label = last_two_day.strftime("%Y%m%d%H")
    forecast_hours = forecast_time_24h.total_seconds() / 3600
    forecast_time_label = f"{int(forecast_hours):03d}"
    return Path(
        meso_gfs_grib2_orig_dir.format(
            start_time_label=start_time_label,
        ),
        "rmf.hgra.{start_time_label}{forecast_time_label}.grb2".format(
            start_time_label=start_time_label,
            forecast_time_label=forecast_time_label,
        ),
    )
