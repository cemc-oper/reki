import pytest
import pandas as pd


@pytest.fixture
def storage_base():
    return "M:"


@pytest.fixture
def start_time():
    return pd.Timestamp.now().ceil(freq="D") - pd.Timedelta(days=2)


@pytest.fixture
def forecast_time():
    return pd.to_timedelta("24h")
