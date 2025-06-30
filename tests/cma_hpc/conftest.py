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
