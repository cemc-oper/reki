"""reki ``test`` source: fetch well-known test datasets through reki.

Built-in source discovered by the directory scan of
``reki/sources/{name}.py``; ``reki.from_source("test", "ecmwf_ifs", ...)``
works out of the box. This is a test-support facility for reki's test
suite and examples — it is not an operational data channel.

The module is self-contained (following the ``url.py`` precedent):
the fetch backends (WIS HTTP download / music-dir copy / GitHub
release download), the download dispatchers and the ``reki-test-data``
command line interface all live here.

Datasets (named ``<organization>_<model>``):

``cma_gfs`` (legacy alias: ``"gfs"``)
    CMA-GFS (GRAPES-GFS) global field, downloaded live from the CMA
    WIS website (or copied from a mounted music-dir directory).
    **Rolling** semantics: the run time rolls with the calendar and
    files are full global fields (hundreds of MB). Fine for tests;
    **not usable for documentation examples** — results are not
    reproducible.

``ecmwf_ifs``
    Frozen subset of ECMWF IFS HRES 0.25° open data (CC-BY-4.0),
    downloaded from a cedarkit-test-data GitHub release. **Frozen**
    semantics: run date, forecast step, parameters and domain are
    fixed in the release asset name; files are KB–MB in size.
    Intended for documentation examples — reproducible and
    offline-friendly. Use the ``domain`` parameter to select the
    asset: ``"eastasia"`` (2t/2d/10u/10v/msl/tp plus gh/t at 500 hPa and
    t/u/v at 850 hPa over 0–60N, 60–150E)
    or ``"global"`` (2t only, global field, for regrid/area demos).
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

#: supported dataset names (``<organization>_<model>``; a future NCEP
#: GFS dataset would be ``ncep_gfs``).
DATASETS = ("cma_gfs", "ecmwf_ifs")

#: legacy dataset names kept for backward compatibility.
DATASET_ALIASES = {"gfs": "cma_gfs"}


def normalize_dataset_name(dataset_name: str) -> str:
    """Resolve a dataset alias to its canonical name."""
    return DATASET_ALIASES.get(dataset_name, dataset_name)


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
# ecmwf_ifs: frozen ECMWF IFS open-data assets from cedarkit-test-data releases
# ---------------------------------------------------------------------------

#: GitHub release that hosts the frozen assets. Updating the dataset =
#: the test-data repo publishes a new tag + this constant is bumped in
#: a reviewable PR. Old doc branches keep pointing at old tags forever.
ECMWF_IFS_RELEASE_TAG = "v2026.8.1"
ECMWF_IFS_BASE_URL = (
    "https://github.com/cemc-oper/cedarkit-test-data"
    f"/releases/download/{ECMWF_IFS_RELEASE_TAG}"
)

#: frozen assets per domain; run date/step are part of the file name.
ECMWF_IFS_ASSETS = {
    "eastasia": "ifs_eastasia_2026081800_f024.grib2",
    "global": "ifs_global_2026081800_f024.grib2",
}


def download_ecmwf_ifs_data(
    output_dir: Path,
    domain: Literal["eastasia", "global"] = "eastasia",
) -> Path:
    """
    Download a frozen ECMWF IFS test-data asset from GitHub releases.

    Parameters
    ----------
    output_dir : Path
        Output directory for downloaded data.
    domain : str
        Which frozen asset to fetch: ``"eastasia"`` (2t/2d/10u/10v/msl/tp
        plus gh/t at 500 hPa and t/u/v at 850 hPa,
        0–60N, 60–150E, for read/plot examples) or ``"global"`` (2t only,
        global field, for regrid/area operator examples).

    Returns
    -------
    Path
        Path to the downloaded file.
    """
    if domain not in ECMWF_IFS_ASSETS:
        raise ValueError(
            f"unknown ecmwf_ifs domain: {domain!r}, "
            f"expected one of {tuple(ECMWF_IFS_ASSETS)}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    file_name = ECMWF_IFS_ASSETS[domain]
    file_url = f"{ECMWF_IFS_BASE_URL}/{file_name}"
    file_path = output_dir / file_name

    download_file(file_url, file_path)

    metadata = {
        "file_name": file_name,
        "system": "ecmwf_ifs",
        "domain": domain,
        "frozen": True,
        "license": "CC-BY-4.0 (ECMWF IFS open data, modified)",
        "source": "github-release",
        "release_tag": ECMWF_IFS_RELEASE_TAG,
    }
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
        which dataset to fetch: ``"ecmwf_ifs"`` (frozen ECMWF IFS
        subset from a GitHub release; documentation examples) or
        ``"cma_gfs"`` (rolling CMA-GFS from the WIS website or a
        mounted music-dir directory; tests only, not reproducible).
        The legacy name ``"gfs"`` is accepted as an alias of
        ``"cma_gfs"``.
    domain
        for ``"ecmwf_ifs"`` only: which frozen asset to fetch,
        ``"eastasia"`` (default) or ``"global"``.
    output_dir
        directory the data file is downloaded to. Defaults to a
        per-user temp directory. Downloads are idempotent: an existing
        file is reused (see ``reki.sources.url.download_file``).
    source
        for ``"cma_gfs"`` only: fetch backend, ``"wis"`` (HTTP
        download) or ``"music-dir"`` (copy from a mounted directory,
        requires ``storage_base``).
    storage_base
        storage base directory for ``source="music-dir"``.
    start_time
        for ``"cma_gfs"`` only: model start time. Defaults to
        yesterday 00Z.
    forecast_time
        for ``"cma_gfs"`` only: forecast time. Defaults to 24 hours.
    """

    #: not a pytest test class despite the name.
    __test__ = False

    #: fetching the dataset is remote I/O; defer it to first use.
    remote = True

    def __init__(
            self,
            dataset_name: str = "gfs",
            output_dir: Optional[Union[str, Path]] = None,
            domain: Literal["eastasia", "global"] = "eastasia",
            source: Literal["wis", "music-dir"] = "wis",
            storage_base: Optional[str] = None,
            start_time: Optional[pd.Timestamp] = None,
            forecast_time: Optional[pd.Timedelta] = None,
            **kwargs,
    ):
        super().__init__(**kwargs)
        canonical_name = normalize_dataset_name(dataset_name)
        if canonical_name not in DATASETS:
            raise ValueError(
                f"unknown test dataset: {dataset_name!r}, "
                f"expected one of {DATASETS} "
                f"(aliases: {DATASET_ALIASES})"
            )
        self.dataset_name = canonical_name
        self.output_dir = (
            Path(output_dir) if output_dir is not None else DEFAULT_DATA_DIR
        )
        self.domain = domain
        self.fetch_source = source
        self.storage_base = storage_base
        self.start_time = start_time
        self.forecast_time = forecast_time

    def mutate(self) -> Source:
        if self.dataset_name == "ecmwf_ifs":
            path = download_ecmwf_ifs_data(
                output_dir=self.output_dir,
                domain=self.domain,
            )
        else:
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


@download.command("cma_gfs")
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
    default=None,
    help="Output directory (default: the shared test-data cache, "
         "$TMPDIR/cedarkit-test-data)",
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
    output: Path | None,
    storage_base: str | None,
    start_time: str | None,
    forecast_time: str,
):
    """Download rolling CMA-GFS (GRAPES-GFS) test data.

    Rolling semantics: the run time rolls with the calendar and files
    are full global fields (hundreds of MB). For tests only — not
    reproducible, do not use for documentation examples (use the
    frozen ``ecmwf_ifs`` dataset instead).

    ``gfs`` is a legacy alias of this command.
    """
    if start_time:
        if len(start_time) == 10 and start_time.isdigit():
            start_ts = pd.Timestamp(start_time, tz="UTC")
        else:
            start_ts = pd.Timestamp(start_time)
    else:
        start_ts = pd.Timestamp.utcnow().floor(freq="D") - pd.Timedelta(days=1)
    forecast_td = pd.Timedelta(forecast_time)
    output = output if output is not None else DEFAULT_DATA_DIR

    click.echo(f"Dataset: cma_gfs (rolling)")
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


#: legacy alias of the ``cma_gfs`` command.
download.add_command(download_gfs, name="gfs")


@download.command("ecmwf_ifs")
@click.option(
    "--domain",
    type=click.Choice(["eastasia", "global"]),
    default="eastasia",
    help=(
        "Which frozen asset to fetch: eastasia (2t/2d/10u/10v/msl/tp plus "
        "gh/t at 500 hPa and t/u/v at 850 hPa, "
        "0-60N, 60-150E; read/plot examples) or global (2t only, global "
        "field; regrid/area operator examples)"
    ),
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory (default: the shared test-data cache, "
         "$TMPDIR/cedarkit-test-data)",
)
def download_ecmwf_ifs(domain: str, output: Path | None):
    """Download frozen ECMWF IFS open-data (CC-BY-4.0) test data.

    Frozen semantics: run date, forecast step, parameters and domain
    are fixed in the release asset name; files are KB-MB in size.
    Intended for documentation examples — reproducible.
    """
    click.echo(f"Dataset: ecmwf_ifs (frozen, release {ECMWF_IFS_RELEASE_TAG})")
    click.echo(f"Domain: {domain}")
    output = output if output is not None else DEFAULT_DATA_DIR
    click.echo(f"Output directory: {output.absolute()}")
    click.echo("Downloading...")

    try:
        file_path = download_ecmwf_ifs_data(output_dir=output, domain=domain)
        click.echo(f"Downloaded to: {file_path}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    main()
