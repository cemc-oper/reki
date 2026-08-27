"""The lightweight top-level reki CLI."""

from __future__ import annotations

import json

import click

from reki.catalog import CatalogError, load_catalog
from reki.core.source_spec import redact


@click.group()
def cli():
    """Inspect reki configuration without opening data sources."""


def _catalog_options(command):
    command = click.option("--no-user", is_flag=True, help="Do not load the user catalog.")(command)
    return click.option("--no-plugins", is_flag=True, help="Do not load plugin catalogs.")(command)


@cli.group()
def catalog():
    """List, inspect, and resolve logical datasets."""


def _load(no_user, no_plugins):
    try:
        return load_catalog(user=not no_user, plugins=not no_plugins)
    except CatalogError as exc:
        raise click.ClickException(str(exc)) from exc


@catalog.command("list")
@_catalog_options
def list_catalog(no_user, no_plugins):
    for record in _load(no_user, no_plugins).list():
        click.echo(record.dataset_id)


@catalog.command("show")
@_catalog_options
@click.argument("dataset_id")
def show_catalog(no_user, no_plugins, dataset_id):
    _emit(_load(no_user, no_plugins).show(dataset_id))


@catalog.command("resolve")
@_catalog_options
@click.argument("dataset_id")
def resolve_catalog(no_user, no_plugins, dataset_id):
    _emit(_load(no_user, no_plugins).resolve(dataset_id))


def _emit(resolved):
    click.echo(json.dumps({
        "id": resolved.record.dataset_id,
        "aliases": list(resolved.record.aliases),
        "source": {"name": resolved.source.name, "args": list(redact(resolved.source.args)),
                   "kwargs": redact(resolved.source.kwargs)},
        "origin": resolved.origin,
        "replaced_origins": list(resolved.replaced_origins),
    }, default=dict, ensure_ascii=False, indent=2, sort_keys=True))


def main():
    cli()


if __name__ == "__main__":
    main()
