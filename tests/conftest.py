import os
from pathlib import Path

import pandas as pd
import pytest
import yaml


# Fixtures that fetch external test data. Tests requesting any of these are
# automatically marked ``needs_data`` in ``pytest_collection_modifyitems``.
DATA_FIXTURES = frozenset({
    "grib2_gfs_basic_file_path",
    "gfs_basic_dir",
})


def pytest_collection_modifyitems(items):
    for item in items:
        if DATA_FIXTURES & set(item.fixturenames):
            item.add_marker(pytest.mark.needs_data)


@pytest.fixture
def data_base_dir() -> Path:
    """Base directory for downloaded test data.

    Defaults to ``tests/data``; set ``REKI_TEST_DATA_DIR`` to point at a
    pre-seeded copy (e.g. on a shared file system of an offline HPC).
    """
    env_dir = os.environ.get("REKI_TEST_DATA_DIR")
    if env_dir:
        return Path(env_dir)
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
    When there is no local copy and the download fails (e.g. no network),
    the test is skipped.
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

    try:
        source = get_source("test", "gfs", output_dir=gfs_basic_dir, **kwargs)
        return Path(source.mutate().path)
    except Exception as e:
        pytest.skip(f"test data not available (no local copy and download failed): {e}")


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

