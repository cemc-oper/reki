"""Versioned grid request commands; the legacy exploration CLI stays separate."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

import click
import yaml

from cedarkit_query import (
    QueryError, RequestList, Response, dump_value, expand_request, load_request,
    parse_text_request, parse_text_requests,
)


_EXIT_CODES = {
    "invalid_query": 2, "invalid_version": 2, "expansion_limit": 2,
    "not_found": 3, "unknown_dataset": 3, "unknown_parameter": 3,
    "unsupported": 4, "unmapped_parameter": 4, "ambiguous_mapping": 4,
    "multiple_matches": 4, "availability_unknown": 4,
    "permission_denied": 5, "provider_error": 5, "stale_reference": 5,
}


def _response(action: str, status: str, **values) -> Response:
    return Response({"api_version": "cedarkit.response/v1", "action": action,
                     "ok": True, "status": status, **values})


def _pairs(values: tuple[str, ...], label: str) -> dict[str, str]:
    result = {}
    for value in values:
        key, separator, item = value.partition("=")
        if not separator or not key or not item or key in result:
            raise QueryError("invalid_query", f"/cli/{label}", f"{label} requires unique ID=VALUE pairs")
        result[key] = item
    return result


def _input(path: str, input_format: str):
    try:
        source = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise QueryError("invalid_query", "/cli/input", "cannot read request input") from exc
    if input_format == "text":
        return parse_text_requests(source) if "---" in source.splitlines() else parse_text_request(source)
    return load_request(source, format=None if input_format == "auto" else input_format)


def _snapshot(config: dict):
    from reki.catalog import load_catalog
    from reki.catalog.query_binding import CatalogSnapshot, builtin_catalog_snapshot

    path = config["catalog"]
    if path is None:
        try:
            return builtin_catalog_snapshot()
        except ValueError as exc:
            raise QueryError("provider_error", "/cli/catalog", "packaged catalog is invalid") from exc
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise QueryError("invalid_query", "/cli/catalog", "cannot read catalog snapshot") from exc
    version = config["catalog_version"] or "sha256:" + hashlib.sha256(raw).hexdigest()
    try:
        catalog = load_catalog(builtin=False, plugins=False, user=False,
                               explicit=yaml.safe_load(raw))
    except (ValueError, yaml.YAMLError) as exc:
        raise QueryError("invalid_query", "/cli/catalog", "catalog snapshot is invalid") from exc
    return CatalogSnapshot(catalog, version)


def _json_safe(value):
    """Keep metadata and NetCDF attributes within the JSON value domain."""
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items() if item is not None}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        return _json_safe(value.item())
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _write_netcdf(data, path: str) -> None:
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        export = data.copy(deep=False)
        attributes = {}
        for key, value in data.attrs.items():
            if value is None:
                continue
            item = _json_safe(value)
            attributes[key] = item if type(item) in (str, int, float) else json.dumps(item, ensure_ascii=False)
        export.attrs = attributes
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.",
                                         suffix=".nc", delete=False) as stream:
            temporary = Path(stream.name)
        try:
            export.to_netcdf(temporary, engine="scipy")
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    except PermissionError as exc:
        raise QueryError("permission_denied", "/options/output/path", "cannot write NetCDF artifact") from exc
    except (OSError, ValueError, ImportError, TypeError) as exc:
        raise QueryError("provider_error", "/options/output", "cannot encode NetCDF artifact") from exc


def _execute_one(raw, action: str, config: dict) -> Response:
    if raw.action != action:
        raise QueryError("invalid_query", "/action", "request action differs from CLI command")
    if action == "validate":
        return _response(action, "valid")
    if "transforms" in raw.to_dict():
        raise QueryError("unsupported", "/transforms", "CLI transform execution is not available")

    from reki.catalog.query_binding import plan_source_binding
    snapshot = _snapshot(config)
    prepared = expand_request(raw, catalog_snapshot=snapshot.aliases())
    normalized = prepared.normalized_request
    plan = plan_source_binding(normalized.query, snapshot=snapshot,
                               local_config_version=config["local_config_version"])
    common = {"query_id": plan.query_id, "binding_id": plan.binding_id,
              "catalog_version": plan.catalog_version}
    if action == "plan":
        return _response(action, "planned", **common, details={
            "normalized_request": normalized.to_dict(),
            "expanded_requests": [item.to_dict() for item in prepared.expanded_requests],
            "binding": plan.to_display_dict(),
        })

    from reki.query_locator import list_fields, locate_fields
    index_dir = Path(config["index_dir"]) if config["index_dir"] else None
    locator_options = {"local_config_dir": Path(config["local_config_dir"])
                       if config["local_config_dir"] else None,
                       "index_dir": index_dir, "index_policy": config["index_policy"]}
    if action == "list":
        report = list_fields(plan, **locator_options)
        fields = [{"path": item.path, "fingerprint": item.fingerprint,
                   "metadata": _json_safe(item.metadata.to_dict())} for item in report.fields]
        return _response(action, report.status, **common, details={"fields": fields})
    if action == "locate":
        policy = normalized.to_dict()["policy"]
        report = locate_fields(plan, native_parameters=_pairs(config["native_parameters"], "native-parameter"),
                               member_roles=_pairs(config["member_roles"], "member-role"),
                               missing=policy["missing"], **locator_options)
        items = [{"field_identity": item.field_identity, "verification": item.verification,
                  **({"path": item.path} if item.path else {}),
                  **({"reference": item.reference.to_dict()} if item.reference else {})}
                 for item in report.items]
        missing = [{"field_identity": item.field_identity,
                    "code": "availability_unknown" if item.verification == "remote_unverified" else "not_found"}
                   for item in report.items if item.verification != "field_confirmed"]
        return _response(action, report.status, **common,
                         references=[reference.to_dict() for reference in report.references],
                         missing=missing, details={"items": items})

    output = normalized.to_dict().get("options", {}).get("output")
    if output is None:
        raise QueryError("invalid_query", "/options/output", "CLI read requires an explicit NetCDF output")
    if isinstance(raw, RequestList):
        raise QueryError("unsupported", "/requests", "CLI read requires one request")
    if plan.binding.kind == "cmadaas":
        from reki.query_cmadaas import read_frozen_cmadaas
        if config["registry_sha256"] is None:
            raise QueryError("invalid_query", "/cli/registry-sha256", "CMADaaS read needs a registry SHA256")
        try:
            result = read_frozen_cmadaas(plan, registry_sha256=config["registry_sha256"])
        except ImportError as exc:
            raise QueryError("unsupported", "/binding/kind", "CMADaaS client is unavailable") from exc
        data, references = result.data, []
        missing = []
    else:
        from reki.query_collection import read_grib_collection
        from reki.query_locator import _path
        candidates = config["candidates"] or tuple(str(_path(plan, item.query.to_dict(),
                                local_config_dir=locator_options["local_config_dir"]))
                                                for item in prepared.expanded_requests)
        result = read_grib_collection(plan, candidate_paths=candidates,
                                      native_parameters=_pairs(config["native_parameters"], "native-parameter"),
                                      member_roles=_pairs(config["member_roles"], "member-role"),
                                      missing=normalized.to_dict()["policy"]["missing"],
                                      **locator_options)
        data = result.data
        references = [field.reference.to_dict() for field in result.fields]
        missing = [{"field_identity": identity, "code": "not_found"} for identity in result.missing]
        missing.extend({"field_identity": identity, "code": "not_found"}
                       for identity in result.expected if result.missing_paths and identity not in result.missing)
    if data is None:
        return _response(action, "partial", **common, references=references, missing=missing)
    _write_netcdf(data, output["path"])
    return _response(action, "available", **common, references=references,
                     artifact={"format": "netcdf", "path": output["path"]})


def _run(action: str, path: str, input_format: str, config: dict) -> None:
    try:
        raw = _input(path, input_format)
        if isinstance(raw, RequestList):
            if action == "read":
                raise QueryError("unsupported", "/requests", "CLI read requires one request")
            responses = [_execute_one(item, action, config) for item in raw.requests]
            click.echo(json.dumps([item.to_dict() for item in responses], ensure_ascii=False,
                                  sort_keys=True, separators=(",", ":")))
        else:
            click.echo(dump_value(_execute_one(raw, action, config)))
    except QueryError as exc:
        if exc.code in {"incompatible_grid", "incompatible_units"}:
            exc = QueryError("unsupported", exc.path, exc.message,
                             {**exc.context, "reason": exc.code})
        elif exc.code not in _EXIT_CODES:
            exc = QueryError("provider_error", exc.path, exc.message,
                             {**exc.context, "reason": exc.code})
        response = Response({"api_version": "cedarkit.response/v1", "action": action,
                             "ok": False, "status": "unknown", "error": exc.to_dict()})
        click.echo(dump_value(response))
        raise click.exceptions.Exit(_EXIT_CODES.get(exc.code, 5)) from exc


@click.group("request")
@click.option("--catalog", type=click.Path(dir_okay=False, path_type=str), help="Explicit catalog snapshot YAML.")
@click.option("--catalog-version", help="Version label for the explicit catalog; defaults to its SHA256.")
@click.option("--local-config-version", help="Version label for a reki-local configuration.")
@click.option("--local-config-dir", type=click.Path(file_okay=False, path_type=str))
@click.option("--native-parameter", "native_parameters", multiple=True, metavar="ID=SHORTNAME")
@click.option("--member-role", "member_roles", multiple=True, metavar="ID=ROLE")
@click.option("--candidate", "candidates", multiple=True, type=click.Path(dir_okay=False, path_type=str))
@click.option("--index-policy", type=click.Choice(["off", "auto", "readonly", "refresh"]), default="off")
@click.option("--index-dir", type=click.Path(file_okay=False, path_type=str))
@click.option("--registry-sha256", help="Pinned parameter registry for frozen CMADaaS reads.")
@click.pass_context
def request(ctx, **config):
    """Run a versioned grid request and emit one JSON response per action."""
    ctx.obj = config


def _action(name: str):
    @request.command(name)
    @click.option("--input", "path", default="-", show_default=True,
                  type=click.Path(dir_okay=False, path_type=str), help="Request file or stdin (-).")
    @click.option("--input-format", type=click.Choice(["auto", "json", "yaml", "text"]),
                  default="auto", show_default=True)
    @click.pass_obj
    def command(config, path, input_format):
        _run(name, path, input_format, config)
    return command


for _name in ("validate", "plan", "list", "locate", "read"):
    _action(_name)
