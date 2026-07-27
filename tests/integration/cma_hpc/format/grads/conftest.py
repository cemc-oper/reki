import pytest
import pandas as pd

from reki.data_finder import find_local_file


@pytest.fixture
def storage_base():
    return "/mnt/m/archive"


@pytest.fixture
def start_time():
    return pd.Timestamp.now().ceil(freq="D") - pd.Timedelta(days=2)


@pytest.fixture
def forecast_time():
    return pd.to_timedelta("24h")


@pytest.fixture
def system_name():
    return "cma_meso_3km"


@pytest.fixture
def file_path(system_name, start_time, storage_base):
    f = find_local_file(
        f"{system_name}/bin/postvar_ctl",
        start_time=start_time,
        storage_base=storage_base
    )
    return f


@pytest.fixture
def modelvar_file_path(system_name, start_time, storage_base):
    f = find_local_file(
        f"{system_name}/bin/modelvar_ctl",
        start_time=start_time,
        storage_base=storage_base
    )
    return f
