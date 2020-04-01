import click
import pandas as pd

from ._config import (
    get_default_local_config_path,
    find_config,
    load_config,
)

from ._util import find_file


def main():
    cli()


@click.group()
def cli():
    pass


@cli.command("local", context_settings=dict(
    ignore_unknown_options=True,
))
@click.option("--data-type", required=True, help="data type, such as grapes_gfs_gmf/grib2/orig")
@click.option("--data-level", default="archive", type=click.Choice(["archive", "storage"]), help="data level")
@click.option("--config-dir", default=None, help="config directory")
@click.argument('query_args', nargs=-1, type=click.UNPROCESSED)
def find_local(data_type, data_level, config_dir, query_args):
    if config_dir is None:
        config_dir = get_default_local_config_path()

    config_file_path = find_config(config_dir, data_type)
    if config_file_path is None:
        raise ValueError(f"data type is not found: {data_type}")

    config = load_config(config_file_path)

    stream = config["query"]["stream"]

    if stream == "oper":
        find_oper_file(config, data_level, query_args)
    elif stream == "eps":
        find_eps_file(config, data_level, query_args)
    else:
        raise ValueError(f"stream type is not supported: {stream}")


def find_oper_file(config: dict, data_level: str, query_args: tuple):
    parser = click.OptionParser()
    parser.add_option(["--start-time"], dest='start_time')
    parser.add_option(["--forecast-time"], dest='forecast_time')
    (values, args, order) = parser.parse_args(list(query_args))

    forecast_time = pd.to_timedelta(values["forecast_time"])
    start_time = pd.to_datetime(values["start_time"], format="%Y%m%d%H")

    file_path = find_file(config, data_level, start_time, forecast_time)
    if file_path is None:
        print("None")
    else:
        print(file_path)


def find_eps_file(config: dict, data_level: str, query_args: tuple):
    parser = click.OptionParser()
    parser.add_option(["--start-time"], dest='start_time')
    parser.add_option(["--forecast-time"], dest='forecast_time')
    parser.add_option(["--number"], dest='number')
    (values, args, order) = parser.parse_args(list(query_args))

    forecast_time = pd.to_timedelta(values["forecast_time"])
    start_time = pd.to_datetime(values["start_time"], format="%Y%m%d%H")

    file_path = find_file(config, data_level, start_time, forecast_time, number=int(values["number"]))
    if file_path is None:
        print("None")
    else:
        print(file_path)


if __name__ == "__main__":
    cli()
