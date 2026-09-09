import argparse

import click

from reki.sources.local import LocalSource


def main():
    cli()


def print_local_help(ctx, param, value):
    if value is False:
        return
    click.echo(ctx.get_help())

    click.echo("\nAdditional query options (number is only used by eps streams):\n")

    parser = create_query_option_parser()
    click.echo(parser.format_help())

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
    """Find a local data file path (implemented by LocalSource)."""
    parser = create_query_option_parser()
    args = parser.parse_args(query_args)

    if data_level == "":
        data_level = None
    else:
        data_level = data_level.split(",")

    kwargs = {}
    if args.number is not None:
        kwargs["number"] = args.number

    src = LocalSource(
        data_type,
        args.start_time,
        args.forecast_time,
        data_level=data_level,
        data_class=data_class,
        config_dir=config_dir,
        **kwargs,
    )
    file_path = src.resolve_path()
    if file_path is None:
        print("None")
    else:
        print(file_path)


def create_query_option_parser():
    parser = argparse.ArgumentParser(
        description='Additional query options.',
        usage=None,
        add_help=False
    )
    parser.add_argument(
        '--start-time',
        dest="start_time",
        required=True,
        help='start time, such as YYYYMMDDHH'
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
        default=None,
        help='member number for eps streams')
    return parser


if __name__ == "__main__":
    cli()
