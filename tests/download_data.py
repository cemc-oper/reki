"""
Download test data for reki through the built-in ``test`` source.
"""
import shutil
from pathlib import Path

import click

from reki.sources import get_source


def download_test_data(gfs_basic_dir: Path, **kwargs) -> Path:
    """Fetch the GFS test file into ``gfs_basic_dir`` via the ``test`` source."""
    source = get_source("test", "gfs", output_dir=gfs_basic_dir, **kwargs)
    return Path(source.mutate().path)


def clear_directory(dir_path: Path) -> None:
    """Clear all contents in a directory."""
    if not dir_path.is_dir():
        raise ValueError(f"{dir_path} is not a valid directory.")

    for item in dir_path.iterdir():
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        except Exception as e:
            print(f"error has found when deleting {item}: {e}")


@click.group()
def cli():
    pass


@cli.command("wis")
def wis():
    """Download test data from CMA WIS service."""
    click.echo("This tool is used to download test data for reki from Internet.")

    data_root_dir = Path(__file__).parent / "data"
    gfs_basic_dir = data_root_dir / "gfs_basic"

    click.echo("creating gfs_basic directory...")
    gfs_basic_dir.mkdir(parents=True, exist_ok=True)
    click.echo("creating gfs_basic directory...done")

    click.echo("deleting everything in gfs_basic directory...")
    clear_directory(gfs_basic_dir)
    click.echo("deleting everything in gfs_basic directory...done")

    click.echo("downloading file...")
    file_path = download_test_data(gfs_basic_dir, source="wis")
    click.echo(f"file is downloaded to: {file_path}")
    click.echo("downloading file...done")


@cli.command("music-dir")
@click.option("--storage-base", required=True, help="storage base directory, such as M:")
def music_dir(storage_base: str):
    """Copy test data from mounted directory by music-dir app."""
    click.echo("This tool is used to copy test data from mounted directory by music-dir app.")

    data_root_dir = Path(__file__).parent / "data"
    gfs_basic_dir = data_root_dir / "gfs_basic"

    click.echo("creating gfs_basic directory...")
    gfs_basic_dir.mkdir(parents=True, exist_ok=True)
    click.echo("creating gfs_basic directory...done")

    click.echo("deleting everything in gfs_basic directory...")
    clear_directory(gfs_basic_dir)
    click.echo("deleting everything in gfs_basic directory...done")

    click.echo("copying file...")
    file_path = download_test_data(
        gfs_basic_dir, source="music-dir", storage_base=storage_base
    )
    click.echo(f"file is downloaded to: {file_path}")
    click.echo("copying file...done")


if __name__ == '__main__':
    cli()
