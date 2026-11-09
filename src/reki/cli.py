"""The top-level reki CLI.

Data exploration commands deliberately delegate to the public reader API.
They never import a format-specific scanner or an index implementation.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict

import click

from cedarkit_query import QueryError, SourceError
from reki.catalog import load_catalog
from reki.catalog.current import current_registration
from reki.catalog.loader import load_resource
from reki.diagnostics import collect_io_metrics
from reki.sources import from_source
from reki.query_cli import request


EXIT_NO_MATCH = 3
EXIT_UNSUPPORTED = 4
EXIT_INDEX_FAILURE = 5


class ExplorationError(click.ClickException):
    """A user-facing exploration failure with a documented exit status."""

    def __init__(self, message, exit_code=1):
        super().__init__(message)
        self.exit_code = exit_code


@click.group()
def cli():
    """Inspect reki configuration and local data files."""


cli.add_command(request)


@cli.group()
def catalog():
    """List and inspect native dataset locators."""


@catalog.command("list")
def list_catalog():
    for dataset in load_catalog().to_dict()["datasets"]:
        click.echo(dataset["id"])


@catalog.command("show")
@click.argument("dataset_id")
def show_catalog(dataset_id):
    try:
        catalog = load_resource({"builtin": "reki.catalog"}, "catalog")
    except (QueryError, SourceError) as exc:
        raise click.ClickException(exc.message) from exc
    for dataset in catalog.value.to_dict()["datasets"]:
        if dataset_id in (dataset["id"], *dataset.get("aliases", ())):
            layout = current_registration(catalog, dataset["id"]) or {}
            click.echo(json.dumps({**dataset, **layout}, ensure_ascii=False, indent=2))
            return
    raise click.ClickException(f"unknown dataset {dataset_id!r}")


def _index_options(command):
    command = click.option("--index-dir", type=click.Path(file_okay=False, path_type=str),
                           help="Retired index directory option; no directory is accessed.")(command)
    command = click.option("--refresh-index", is_flag=True,
                           help="Retired; requesting index refresh is unsupported.")(command)
    command = click.option("--read-only-index", is_flag=True,
                           help="Retired; requesting index reads is unsupported.")(command)
    command = click.option("--use-index", is_flag=True,
                           help="Retired; requesting an index is unsupported.")(command)
    return click.option("--no-index", is_flag=True,
                        help="Do not read or write a metadata index.")(command)


def _query_options(command):
    command = click.option("--extra", multiple=True, metavar="KEY=VALUE",
                           help="Native GRIB key filter; VALUE may be JSON.")(command)
    command = click.option("--member", type=int, multiple=True)(command)
    command = click.option("--time-range")(command)
    command = click.option("--step-type")(command)
    command = click.option("--step", type=float,
                           help="Native GRIB forecast step filter in hours.")(command)
    command = click.option("--level", type=float, multiple=True)(command)
    command = click.option("--level-type")(command)
    return click.option("--parameter")(command)


def _output_options(command):
    command = click.option("--verbose", is_flag=True,
                           help="Report index hit/miss counters on stderr.")(command)
    command = click.option("--offset", type=click.IntRange(min=0), default=0,
                           show_default=True, help="Metadata row offset.")(command)
    command = click.option("--limit", type=click.IntRange(min=0), default=100,
                           show_default=True, help="Maximum metadata rows to print.")(command)
    return click.option("--json", "as_json", is_flag=True,
                        help="Emit stable JSON instead of a table.")(command)


def _index_policy(use_index, no_index, read_only_index, refresh_index):
    choices = sum((bool(option) for option in
                   (use_index, no_index, read_only_index, refresh_index)))
    if choices > 1:
        raise click.UsageError("--use-index, --no-index, --read-only-index, and --refresh-index are mutually exclusive")
    if use_index:
        return "auto"
    if no_index:
        return "off"
    if read_only_index:
        return "readonly"
    if refresh_index:
        return "refresh"
    return "off"


def _parse_extra(values):
    extra = {}
    for item in values:
        if "=" not in item:
            raise click.BadParameter("must use KEY=VALUE", param_hint="--extra")
        key, value = item.split("=", 1)
        if not key or key in extra:
            raise click.BadParameter("keys must be non-empty and unique", param_hint="--extra")
        try:
            extra[key] = json.loads(value)
        except json.JSONDecodeError:
            extra[key] = value
    return extra


def _query_from_options(parameter, level_type, level, step, step_type, time_range, member, extra):
    values = _parse_extra(extra)
    if step is not None:
        if "step" in values:
            raise click.BadParameter("cannot be combined with --extra step=...", param_hint="--step")
        values["step"] = step
    if parameter is not None:
        values["parameter"] = parameter
    if level_type is not None:
        values["level_type"] = level_type
    if level:
        values["level"] = level[0] if len(level) == 1 else list(level)
    if step_type is not None:
        values["step_type"] = step_type
    if time_range is not None:
        values["time_range"] = time_range
    if member:
        values["member"] = member[0] if len(member) == 1 else list(member)
    return values


def _open_reader(path, *, use_index, no_index, read_only_index, refresh_index, index_dir):
    policy = _index_policy(use_index, no_index, read_only_index, refresh_index)
    try:
        return from_source("file", path, index_policy=policy, index_dir=index_dir)
    except FileNotFoundError as exc:
        raise ExplorationError(str(exc), EXIT_UNSUPPORTED) from exc
    except ValueError as exc:
        raise ExplorationError(str(exc), EXIT_UNSUPPORTED) from exc


def _metadata_keys(keys):
    if keys is None:
        return None
    result = tuple(key.strip() for key in keys.split(",") if key.strip())
    if not result or len(set(result)) != len(result):
        raise click.BadParameter("must contain non-empty, non-duplicate comma-separated keys",
                                 param_hint="--keys")
    return result


def _emit_metadata(fields, *, keys, offset, limit, as_json):
    rows = fields[offset:offset + limit]
    try:
        if as_json:
            click.echo(json.dumps(rows.json(keys), ensure_ascii=False, sort_keys=True,
                                  separators=(",", ":"), default=str))
        else:
            frame = rows.ls(keys)
            click.echo(frame.to_string(index=False) if len(frame) else "No fields matched.")
    except KeyError as exc:
        raise click.BadParameter(str(exc), param_hint="--keys") from exc


def _emit_inspect(reader, metrics, as_json):
    try:
        result = {
            "path": os.path.basename(str(reader.path)),
            "reader": type(reader).__name__,
            "capabilities": asdict(reader.capabilities),
            "summary": reader.summary(),
            "metrics": metrics.snapshot().to_dict(),
        }
    except QueryError as exc:
        raise ExplorationError(str(exc), EXIT_UNSUPPORTED) from exc
    if as_json:
        click.echo(json.dumps(result, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":"), default=str))
    else:
        click.echo(f"{result['reader']}: {result['path']}")
        for key, value in result["summary"].items():
            click.echo(f"{key}: {value}")


def _emit_index_metrics(metrics, verbose):
    """Keep diagnostics off stdout so JSON remains machine-readable."""
    if not verbose:
        return
    snapshot = metrics.snapshot()
    reasons = snapshot.index_miss_reasons
    suffix = "" if not reasons else f", reasons={dict(reasons)}"
    click.echo(
        f"index: hits={snapshot['index_hit_count']}, misses={snapshot['index_miss_count']}, "
        f"builds={snapshot['index_build_count']}, rebuilds={snapshot['index_rebuild_count']}{suffix}",
        err=True,
    )


@cli.command("inspect")
@click.argument("path", type=click.Path(dir_okay=False, path_type=str))
@click.option("--json", "as_json", is_flag=True, help="Emit stable JSON.")
@click.option("--verbose", is_flag=True, help="Report index counters on stderr.")
@_index_options
def inspect(path, as_json, verbose, use_index, no_index, read_only_index, refresh_index, index_dir):
    """Show metadata-only information about a local file."""
    with collect_io_metrics() as metrics:
        reader = _open_reader(path, use_index=use_index, no_index=no_index, read_only_index=read_only_index,
                              refresh_index=refresh_index, index_dir=index_dir)
        _emit_inspect(reader, metrics, as_json)
        _emit_index_metrics(metrics, verbose)


def _list_fields(path, parameter, level_type, level, step, step_type, time_range, member, extra,
                 use_index, no_index, read_only_index, refresh_index, index_dir):
    reader = _open_reader(path, use_index=use_index, no_index=no_index, read_only_index=read_only_index,
                          refresh_index=refresh_index, index_dir=index_dir)
    try:
        if not reader.capabilities.field_list:
            reader._unsupported("metadata")
        return reader.sel(**_query_from_options(parameter, level_type, level, step, step_type,
                                                time_range, member, extra)).all()
    except QueryError as exc:
        raise ExplorationError(str(exc), EXIT_UNSUPPORTED) from exc
    except (OSError, ValueError) as exc:
        code = EXIT_INDEX_FAILURE if refresh_index else EXIT_UNSUPPORTED
        raise ExplorationError(str(exc), code) from exc


@cli.command("ls")
@click.argument("path", type=click.Path(dir_okay=False, path_type=str))
@click.option("--keys", help="Comma-separated metadata columns.")
@_query_options
@_output_options
@_index_options
def ls(path, keys, parameter, level_type, level, step, step_type, time_range, member, extra,
       limit, offset, as_json, verbose, use_index, no_index, read_only_index, refresh_index, index_dir):
    """List matching field metadata without decoding values."""
    with collect_io_metrics() as metrics:
        fields = _list_fields(path, parameter, level_type, level, step, step_type, time_range, member,
                              extra, use_index, no_index, read_only_index, refresh_index, index_dir)
        _emit_metadata(fields, keys=_metadata_keys(keys), offset=offset, limit=limit, as_json=as_json)
        _emit_index_metrics(metrics, verbose)


@cli.command("query")
@click.argument("path", type=click.Path(dir_okay=False, path_type=str))
@click.option("--keys", help="Comma-separated metadata columns.")
@_query_options
@_output_options
@_index_options
def query(path, keys, parameter, level_type, level, step, step_type, time_range, member, extra,
          limit, offset, as_json, verbose, use_index, no_index, read_only_index, refresh_index, index_dir):
    """Query a local file and print matching metadata only."""
    with collect_io_metrics() as metrics:
        fields = _list_fields(path, parameter, level_type, level, step, step_type, time_range, member,
                              extra, use_index, no_index, read_only_index, refresh_index, index_dir)
        _emit_metadata(fields, keys=_metadata_keys(keys), offset=offset, limit=limit, as_json=as_json)
        _emit_index_metrics(metrics, verbose)
        if not fields:
            raise click.exceptions.Exit(EXIT_NO_MATCH)


def main():
    cli()


if __name__ == "__main__":
    main()
