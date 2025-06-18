import shutil
from pathlib import Path
from urllib.parse import urlparse

import yaml
from tqdm import tqdm
import requests
import pandas as pd
import click

gfs_base_url_template = "http://data.wis.cma.cn/DCPC_WMC_BJ/open/nwp/gmf_gra/t{start_hour_str}00/f0_f240_6h/"
gfs_file_name_template = "Z_NAFP_C_BABJ_{start_time_str}0000_P_NWPC-GRAPES-GFS-GLB-{forecast_hour_str}00.grib2"

@click.command()
def cli():
    click.echo("This tool is used to download test data for reki from Internet.")
    start_time = pd.Timestamp.utcnow().ceil(freq="D") - pd.Timedelta(days=1)

    data_root_dir = Path(__file__).parent / "data"
    data_root_dir.mkdir(exist_ok=True)

    click.echo("creating gfs_basic directory...")
    gfs_basic_dir = data_root_dir / "gfs_basic"
    gfs_basic_dir.mkdir(exist_ok=True)
    click.echo("creating gfs_basic directory...done")

    click.echo("deleting everything in gfs_basic directory...")
    clear_directory(gfs_basic_dir)
    click.echo("deleting everything in gfs_basic directory...done")

    forecast_time = pd.Timedelta(hours=24)
    file_url = get_gfs_file_url(start_time, forecast_time)
    click.echo(f"file url to be downloaded: {file_url}")

    parsed_url = urlparse(file_url)
    path = parsed_url.path
    file_name = path.rstrip('/').split('/')[-1]
    file_path = gfs_basic_dir / file_name
    click.echo(f"file is downloaded to: {file_path}")

    click.echo("writing metadata file...")
    metadata_file_path = gfs_basic_dir / "metadata.yaml"
    metadata = [
        {
            "file_name": file_name,
            "system": "cma_gfs",
            "start_time": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "forecast_time": forecast_time.isoformat(),
            "source": "wis",
        }
    ]
    with open(metadata_file_path, "w") as f:
        yaml.safe_dump(metadata, f, default_flow_style=False)
    click.echo("writing metadata file...")

    click.echo("downloading file...")
    download_file(url=file_url, file_path=file_path)
    click.echo("downloading file...done")

def clear_directory(dir_path):
    p = Path(dir_path)
    if not p.is_dir():
        raise ValueError(f"{dir_path} is not a valid directory.")

    for item in p.iterdir():
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        except Exception as e:
            print(f"error has found when deleting {item}: {e}")


def get_gfs_file_url(start_time: pd.Timestamp, forecast_time: pd.Timedelta) -> str:
    start_hour_str = start_time.strftime("%H")
    start_time_str = start_time.strftime("%Y%m%d%H")
    forecast_hour_str = f"{int(forecast_time / pd.Timedelta(hours=1)):03}"

    file_url = gfs_base_url_template.format(
        start_hour_str=start_hour_str,
    ) + gfs_file_name_template.format(
        start_time_str=start_time_str,
        forecast_hour_str=forecast_hour_str
    )

    return file_url


def download_file(url: str, file_path: Path):
    file_name = file_path.name
    response = requests.head(url)
    total_size = int(response.headers.get('content-length', 0))

    with requests.get(url, stream=True) as r, open(file_path, 'wb') as f, tqdm(
        total=total_size, unit='B', unit_scale=True, desc=file_name
    ) as progress_bar:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
                progress_bar.update(len(chunk))


if __name__ == '__main__':
    cli()
