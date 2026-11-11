"""Run a native Query request from a JSON or YAML file."""

import errno
import json
import os
from pathlib import Path
from stat import S_IMODE, S_ISREG
from tempfile import TemporaryDirectory

import click

from cedarkit_query import QueryError, Request, SourceError, dump_value
from reki import from_source


class _RequestFailure(click.ClickException):
    """Emit the public error without Click's human-readable prefix."""

    def show(self, file=None):
        click.echo(self.message, file=file, err=True)


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


def _write_netcdf(dataset, path):
    context = {"resource": str(path), "operation": "write_netcdf"}
    try:
        destination = path.resolve()
        try:
            mode = destination.stat().st_mode
        except FileNotFoundError:
            mode = None
        if mode is not None:
            if not S_ISREG(mode):
                raise SourceError("io_error", "/output", "NetCDF destination must be a regular file", context)
            os.close(os.open(destination, os.O_WRONLY))

        with TemporaryDirectory(dir=destination.parent, prefix=".reki-") as directory:
            staged = Path(directory) / destination.name
            dataset.to_netcdf(staged)
            if mode is not None:
                staged.chmod(S_IMODE(mode))
            staged.replace(destination)
    except OSError as exc:
        code = {
            errno.ENOENT: "resource_not_found",
            errno.EACCES: "permission_denied",
            errno.EPERM: "permission_denied",
        }.get(exc.errno, "io_error")
        raise SourceError(code, "/output", str(exc), context) from exc


def _run(path, action, output_path=None):
    try:
        declaration = Request.load(path)
        dataset = None
        with from_source(declaration.source, context=declaration.context) as source:
            selection = source.sel(declaration.queries)
            if action == "explain":
                result = dump_value(selection.explain())
            else:
                fields = selection.all(completeness=declaration.completeness)
                if output_path is not None:
                    dataset = fields.to_xarray()
                result = fields.report.to_json()
        if dataset is not None:
            _write_netcdf(dataset, output_path)
    except (QueryError, SourceError) as exc:
        raise _RequestFailure(json.dumps(exc.to_dict(), ensure_ascii=False)) from exc
    click.echo(result)
