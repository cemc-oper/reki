"""Run a native Query request from a JSON or YAML file."""

from pathlib import Path

import click

from cedarkit_query import QueryError, Request, SourceError, dump_value
from reki import from_source


@click.group("request")
def request():
    """Inspect, list or read fields in a native Query request."""


@request.command("explain")
@click.argument(
    "input_path", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
def explain(input_path):
    _run(input_path, "explain")


@request.command("list")
@click.argument(
    "input_path", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
def list_fields(input_path):
    _run(input_path, "list")


@request.command("read")
@click.argument(
    "input_path", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.argument("output_path", type=click.Path(dir_okay=False, path_type=Path))
def read_fields(input_path, output_path):
    _run(input_path, "read", output_path)


def _run(path, action, output_path=None):
    try:
        declaration = Request.load(path)
        with from_source(declaration.source, context=declaration.context) as source:
            selection = source.sel(declaration.queries)
            if action == "explain":
                click.echo(dump_value(selection.explain()))
            else:
                fields = selection.all(completeness=declaration.completeness)
                if output_path is not None:
                    fields.to_xarray().to_netcdf(output_path)
                click.echo(fields.report.to_json())
    except (QueryError, SourceError) as exc:
        raise click.ClickException(f"{exc.code} {exc.path}: {exc.message}") from exc
