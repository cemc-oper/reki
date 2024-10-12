import argparse
from typing import Union

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


def print_local_help(ctx, param, value):
    if value is False:
        return
    click.echo(ctx.get_help())

    click.echo("\nDifferent steams use different additional options.\n")

    oper_parser = create_oper_option_parser()
    click.echo(oper_parser.format_help())

    eps_parser = create_eps_option_parser()
    click.echo(eps_parser.format_help())

    ctx.exit()


@click.group()
def cli():
    pass


@cli.command("local", context_settings=dict(
    ignore_unknown_options=True,
))
@click.option("--data-type", required=True, help="data type, such as cma_gfs_gmf/grib2/orig")
@click.option("--data-level", default="archive,storage", help="data level, split by comma, such as archive,storage")
@click.option("--data-class", default="od", help="data class, such as od for operation data, or cm for common data.")
@click.option("--config-dir", default=None, help="config directory")
@click.option(
    "--help", "-h",
    is_flag=True,
    expose_value=False,
    is_eager=True,
    callback=print_local_help,
    help="Show this message and exit.")
@click.argument('query_args', nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def find_local(ctx, data_type, data_level, data_class, config_dir, query_args):
    if config_dir is None:
        config_dir = get_default_local_config_path()

    config_file_path = find_config(config_dir, data_type, data_class)
    if config_file_path is None:
        raise ValueError(f"data type is not found: {data_type}")

    if data_level == "":
        data_level = None
    else:
        data_level = data_level.split(",")

    config = load_config(config_file_path)

    stream = config["query"]["stream"]

    if stream in ("oper", "cm"):
        find_oper_file(config, data_level, query_args)
    elif stream == "eps":
        find_eps_file(config, data_level, query_args)
    else:
        raise ValueError(f"stream type is not supported: {stream}")


def find_oper_file(config: dict, data_level: Union[str, list[str]], query_args: tuple):
    parser = create_oper_option_parser()
    args = parser.parse_args(query_args)

    forecast_time = pd.to_timedelta(args.forecast_time)
    start_time = pd.to_datetime(args.start_time, format="%Y%m%d%H")

    file_path = find_file(config, data_level, start_time, forecast_time)
    if file_path is None:
        print("None")
    else:
        print(file_path)


def find_eps_file(config: dict, data_level: Union[str, list[str]], query_args: tuple):
    parser = create_eps_option_parser()
    args = parser.parse_args(query_args)

    forecast_time = pd.to_timedelta(args.forecast_time)
    start_time = pd.to_datetime(args.start_time, format="%Y%m%d%H")

    file_path = find_file(config, data_level, start_time, forecast_time, number=args.number)
    if file_path is None:
        print("None")
    else:
        print(file_path)


def create_oper_option_parser():
    parser = argparse.ArgumentParser(
        description='Additional options for stream oper.',
        usage=None,
        add_help=False
    )
    parser.add_argument(
        '--start-time',
        dest="start_time",
        help='start time, such as YYYMMDDHH'
    )
    parser.add_argument(
        '--forecast-time',
        dest='forecast_time',
        default="0h",
        help='forecast time, such as 3h'
    )
    return parser


def create_eps_option_parser():
    parser = argparse.ArgumentParser(
        description='Additional options for stream eps.',
        usage=None,
        add_help=False
    )
    parser.add_argument(
        '--start-time',
        dest="start_time",
        help='start time, such as YYYMMDDHH'
    )
    parser.add_argument(
        '--forecast-time',
        dest='forecast_time',
        default="0h",
        help='forecast time, such as 3h'
    )
    parser.add_argument(
        '--number',
        dest='number',
        type=int,
        help='member number')
    return parser


# copy from argparse module
def _format_help(parser: argparse.ArgumentParser):
    """
    Notes
    -----
    This is an experimental function. Do not use it.
    """
    formatter = parser._get_formatter()

    # description
    formatter.add_text(parser.description)

    # positionals, optionals and user-defined groups
    for action_group in parser._action_groups:
        formatter.start_section(action_group.title)
        formatter.add_text(action_group.description)
        formatter.add_arguments(action_group._group_actions)
        formatter.end_section()

    # epilog
    # formatter.add_text(parser.epilog)

    # determine help from format above
    return formatter.format_help()


if __name__ == "__main__":
    cli()
