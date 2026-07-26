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
    """Locate the GFS test file, fetching it through the ``test`` source.

    The fetch always goes through the ``test`` source (provided by the
    cedarkit-test-data plugin). When the data was downloaded before, the
    recorded start/forecast time makes the source resolve to the existing
    file, so no network access happens; otherwise the file is downloaded.
    """
    from reki.sources import get_source

    kwargs = {}
    metadata_file = gfs_basic_dir / "metadata.yaml"
    if metadata_file.exists():
        with open(metadata_file, "r") as f:
            metadata = yaml.safe_load(f)
        first_file_metadata = metadata[0]
        kwargs["start_time"] = pd.Timestamp(first_file_metadata["start_time"])
        kwargs["forecast_time"] = pd.Timedelta(first_file_metadata["forecast_time"])

    source = get_source("test", "gfs", output_dir=gfs_basic_dir, **kwargs)
    return Path(source.mutate().path)


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

