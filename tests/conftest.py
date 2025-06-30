from pathlib import Path

import pandas as pd
import pytest
import yaml


@pytest.fixture
def data_base_dir() -> Path:
    return Path(__file__).parent / 'data'


@pytest.fixture
def gfs_basic_dir(data_base_dir) -> Path:
    return data_base_dir / 'gfs_basic'


@pytest.fixture
def grib2_gfs_basic_file_path(gfs_basic_dir) -> Path:
    metadata_file = gfs_basic_dir / "metadata.yaml"
    with open(metadata_file, "r") as f:
        metadata = yaml.safe_load(f)
    first_file_metadata = metadata[0]
    return gfs_basic_dir / first_file_metadata["file_name"]


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

