"""reki ``test`` source: fetch well-known test datasets through reki.

Built-in source discovered by the directory scan of
``reki/sources/{name}.py``; ``reki.from_source("test", "gfs", ...)``
works out of the box. This is a test-support facility for reki's test
suite and examples — it is not an operational data channel.

The module is self-contained (following the ``url.py`` precedent):
the fetch backends (WIS HTTP download / music-dir copy), the
``download_gfs_data`` dispatcher and the ``reki-test-data`` command
line interface all live here.
"""

import shutil
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Literal, Optional, Union

import click
import pandas as pd
import yaml

from reki.core import Source
from reki.sources import get_source
from reki.sources.url import download_file, file_name_from_url

#: default directory for downloaded test data files.
DEFAULT_DATA_DIR = Path(tempfile.gettempdir()) / "cedarkit-test-data"

#: supported dataset names.
DATASETS = ("gfs",)


# ---------------------------------------------------------------------------
# fetch backends
# ---------------------------------------------------------------------------

GFS_BASE_URL_TEMPLATE = "http://data.wis.cma.cn/DCPC_WMC_BJ/open/nwp/gmf_gra/t{start_hour_str}00/f0_f240_6h/"
GFS_FILE_NAME_TEMPLATE = "Z_NAFP_C_BABJ_{start_time_str}0000_P_NWPC-GRAPES-GFS-GLB-{forecast_hour_str}00.grib2"
GFS_BASE_PATH_TEMPLATE = "{storage_base}/DATA/NAFP/NMC/GRAPES-GFS-GLB/{start_year_str}/{start_date_str}/"


class DataSource(ABC):
    """Abstract base class for test data fetch backends."""

    @abstractmethod
    def get_file_path_or_url(
        self,
        start_time: pd.Timestamp,
        forecast_time: pd.Timedelta,
        **kwargs,
    ) -> str | Path:
        """Get the file path or URL for the data file."""
        pass

    @abstractmethod
    def fetch(
        self,
        start_time: pd.Timestamp,
        forecast_time: pd.Timedelta,
        output_dir: Path,
        **kwargs,
    ) -> Path:
        """Fetch the data file to the output directory."""
        pass

    @abstractmethod
    def get_metadata(
        self,
        start_time: pd.Timestamp,
        forecast_time: pd.Timedelta,
        file_name: str,
        **kwargs,
    ) -> dict[str, Any]:
        """Get metadata for the downloaded file."""
        pass


class GfsWisSource(DataSource):
    """GFS data source from CMA WIS website."""

    def get_file_path_or_url(
        self,
        start_time: pd.Timestamp,
        forecast_time: pd.Timedelta,
        **kwargs,
    ) -> str:
        start_hour_str = start_time.strftime("%H")
        start_time_str = start_time.strftime("%Y%m%d%H")
        forecast_hour_str = f"{int(forecast_time / pd.Timedelta(hours=1)):03}"

        file_url = GFS_BASE_URL_TEMPLATE.format(
            start_hour_str=start_hour_str,
        ) + GFS_FILE_NAME_TEMPLATE.format(
            start_time_str=start_time_str,
            forecast_hour_str=forecast_hour_str
        )
        return file_url

    def fetch(
        self,
        start_time: pd.Timestamp,
        forecast_time: pd.Timedelta,
        output_dir: Path,
        **kwargs,
    ) -> Path:
        file_url = self.get_file_path_or_url(start_time, forecast_time)
        file_path = output_dir / file_name_from_url(file_url)

        download_file(file_url, file_path)
        return file_path

    def get_metadata(
        self,
        start_time: pd.Timestamp,
        forecast_time: pd.Timedelta,
        file_name: str,
        **kwargs,
    ) -> dict[str, Any]:
        return {
            "file_name": file_name,
            "system": "cma_gfs",
            "start_time": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "forecast_time": forecast_time.isoformat(),
            "source": "wis",
        }


class GfsMusicDirSource(DataSource):
    """GFS data source from local mounted music-dir directory."""

    def __init__(self, storage_base: str):
        self.storage_base = storage_base

    def get_file_path_or_url(
        self,
        start_time: pd.Timestamp,
        forecast_time: pd.Timedelta,
        **kwargs,
    ) -> Path:
        start_year_str = start_time.strftime("%Y")
        start_date_str = start_time.strftime("%Y%m%d")
        start_time_str = start_time.strftime("%Y%m%d%H")
        forecast_hour_str = f"{int(forecast_time / pd.Timedelta(hours=1)):03}"

        file_path = Path(
            GFS_BASE_PATH_TEMPLATE.format(
                start_year_str=start_year_str,
                start_date_str=start_date_str,
                storage_base=self.storage_base,
            ),
            GFS_FILE_NAME_TEMPLATE.format(
                start_time_str=start_time_str,
                forecast_hour_str=forecast_hour_str
            ),
        )
        return file_path

    def fetch(
        self,
        start_time: pd.Timestamp,
        forecast_time: pd.Timedelta,
        output_dir: Path,
        **kwargs,
    ) -> Path:
        source_file_path = self.get_file_path_or_url(start_time, forecast_time)
        file_name = source_file_path.name
        file_path = output_dir / file_name

        shutil.copy(source_file_path, file_path)
        return file_path

    def get_metadata(
        self,
        start_time: pd.Timestamp,
        forecast_time: pd.Timedelta,
        file_name: str,
        **kwargs,
    ) -> dict[str, Any]:
        return {
            "file_name": file_name,
            "system": "cma_gfs",
            "start_time": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "forecast_time": forecast_time.isoformat(),
            "source": "music-dir",
        }


def download_gfs_data(
    output_dir: Path,
    source: Literal["wis", "music-dir"] = "wis",
    start_time: Optional[pd.Timestamp] = None,
    forecast_time: Optional[pd.Timedelta] = None,
    storage_base: Optional[str] = None,
) -> Path:
    """
    Download GFS test data.

    Parameters
    ----------
    output_dir : Path
        Output directory for downloaded data.
    source : str
        Data source, either "wis" or "music-dir".
    start_time : pd.Timestamp, optional
        Start time. Defaults to yesterday 00Z.
    forecast_time : pd.Timedelta, optional
        Forecast time. Defaults to 24 hours.
    storage_base : str, optional
        Storage base directory for music-dir source.

    Returns
    -------
    Path
        Path to the downloaded file.
    """
    if start_time is None:
        start_time = pd.Timestamp.utcnow().floor(freq="D") - pd.Timedelta(days=1)
    if forecast_time is None:
        forecast_time = pd.Timedelta(hours=24)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Create data source
    data_source: DataSource
    if source == "wis":
        data_source = GfsWisSource()
    elif source == "music-dir":
        if storage_base is None:
            raise ValueError("storage_base is required for music-dir source")
        data_source = GfsMusicDirSource(storage_base=storage_base)
    else:
        raise ValueError(f"Unknown source: {source}")

    # Fetch data
    file_path = data_source.fetch(
        start_time=start_time,
        forecast_time=forecast_time,
        output_dir=output_dir,
    )

    # Write metadata
    metadata = data_source.get_metadata(
        start_time=start_time,
        forecast_time=forecast_time,
        file_name=file_path.name,
    )
    metadata_file_path = output_dir / "metadata.yaml"
    with open(metadata_file_path, "w") as f:
        yaml.safe_dump([metadata], f, default_flow_style=False)

    return file_path


# ---------------------------------------------------------------------------
# reki source
# ---------------------------------------------------------------------------

class TestSource(Source):
    """Fetch a test dataset file, then read it as a local file.

    Parameters
    ----------
    dataset_name
        which dataset to fetch. Currently only ``"gfs"`` (a GRIB2 file
        of CMA-GFS from the WIS website or a mounted music-dir
        directory).
    output_dir
        directory the data file is downloaded to. Defaults to a
        per-user temp directory. Downloads are idempotent: an existing
        file is reused (see ``reki.sources.url.download_file``).
    source
        fetch backend, ``"wis"`` (HTTP download) or ``"music-dir"``
        (copy from a mounted directory, requires ``storage_base``).
    storage_base
        storage base directory for ``source="music-dir"``.
    start_time
        model start time. Defaults to yesterday 00Z.
    forecast_time
        forecast time. Defaults to 24 hours.
    """

    #: not a pytest test class despite the name.
    __test__ = False

    #: fetching the dataset is remote I/O; defer it to first use.
    remote = True

    def __init__(
            self,
            dataset_name: str = "gfs",
            output_dir: Optional[Union[str, Path]] = None,
            source: Literal["wis", "music-dir"] = "wis",
            storage_base: Optional[str] = None,
            start_time: Optional[pd.Timestamp] = None,
            forecast_time: Optional[pd.Timedelta] = None,
            **kwargs,
    ):
        super().__init__(**kwargs)
        if dataset_name not in DATASETS:
            raise ValueError(
                f"unknown test dataset: {dataset_name!r}, "
                f"expected one of {DATASETS}"
            )
        self.dataset_name = dataset_name
        self.output_dir = (
            Path(output_dir) if output_dir is not None else DEFAULT_DATA_DIR
        )
        self.fetch_source = source
        self.storage_base = storage_base
        self.start_time = start_time
        self.forecast_time = forecast_time

    def mutate(self) -> Source:
        path = download_gfs_data(
            output_dir=self.output_dir,
            source=self.fetch_source,
            start_time=self.start_time,
            forecast_time=self.forecast_time,
            storage_base=self.storage_base,
        )
        return get_source("file", path)

    def __repr__(self):
        return f"TestSource({self.dataset_name!r})"


source = TestSource


# ---------------------------------------------------------------------------
# command line interface (reki-test-data)
# ---------------------------------------------------------------------------

@click.group()
@click.version_option()
def main():
    """reki-test-data: test data downloader for reki's test suite."""
    pass


@main.group()
def download():
    """Download test data."""
    pass


@download.command("gfs")
@click.option(
    "--source",
    type=click.Choice(["wis", "music-dir"]),
    default="wis",
    help="Data source (wis or music-dir)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=Path("."),
    help="Output directory",
)
@click.option(
    "--storage-base",
    type=str,
    default=None,
    help="Storage base directory for music-dir source",
)
@click.option(
    "--start-time",
    type=str,
    default=None,
    help="Start time in ISO format (e.g., 2024-01-01T00:00:00Z) or YYYYMMDDHH",
)
@click.option(
    "--forecast-time",
    type=str,
    default="24h",
    help="Forecast time in pd.Timedelta format (e.g., 24h, 1d, 48h)",
)
def download_gfs(
    source: str,
    output: Path,
    storage_base: str | None,
    start_time: str | None,
    forecast_time: str,
):
    """Download GFS test data."""
    if start_time:
        if len(start_time) == 10 and start_time.isdigit():
            start_ts = pd.Timestamp(start_time, tz="UTC")
        else:
            start_ts = pd.Timestamp(start_time)
    else:
        start_ts = pd.Timestamp.utcnow().floor(freq="D") - pd.Timedelta(days=1)
    forecast_td = pd.Timedelta(forecast_time)

    click.echo(f"Source: {source}")
    click.echo(f"Start time: {start_ts.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    click.echo(f"Forecast time: {forecast_time}")
    click.echo(f"Output directory: {output.absolute()}")
    click.echo("Downloading...")

    try:
        file_path = download_gfs_data(
            output_dir=output,
            source=source,
            start_time=start_ts,
            forecast_time=forecast_td,
            storage_base=storage_base,
        )
        click.echo(f"Downloaded to: {file_path}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    main()
