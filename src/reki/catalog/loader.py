"""Explicit, byte-pinned local resources. No environment discovery or fallback."""

import hashlib
import os
from pathlib import Path
from types import MappingProxyType

import cedarkit_query
from cedarkit_query import Context, QueryError, SourceError, load_value

from ._cache import _ResourceCache
from .model import LoadedResource, freeze

# Defaults are activated only by an explicitly registered dataset.
_BUILTIN_DIR = Path(__file__).with_name("builtin")
BUILTINS = MappingProxyType(
    {
        "reki.catalog": _BUILTIN_DIR / "catalog-v1.json",
        "reki.catalog.cmadaas.task07a": _BUILTIN_DIR / "cmadaas-task07a-catalog.json",
        **{
            f"reki.{kind}.cmadaas.current": _BUILTIN_DIR / f"current-cmadaas-{kind}.json"
            for kind in ("parameters", "mappings")
        },
        **{
            f"reki.{kind}.cmadaas.task07a": _BUILTIN_DIR
            / f"cmadaas-task07a-{kind}.json"
            for kind in ("parameters", "mappings")
        },
        **{
            f"reki.{kind}.cma-{system}.current": _BUILTIN_DIR
            / f"current-{system}-{kind}.json"
            for system in ("gfs", "meso1", "meso3", "tym", "geps", "reps")
            for kind in ("parameters", "mappings")
        },
    }
)
_PARSED_RESOURCES = _ResourceCache(maxsize=32)
# cedarkit-query 0.2.1 uses the strict loader.
load_prevalidated_resource = getattr(cedarkit_query, "load_prevalidated_resource", None)


def _read(path, pointer):
    try:
        return path.read_bytes()
    except FileNotFoundError as exc:
        raise SourceError(
            "resource_not_found", pointer, "explicit resource is missing"
        ) from exc
    except PermissionError as exc:
        raise SourceError(
            "permission_denied", pointer, "resource is not readable"
        ) from exc
    except OSError as exc:
        raise SourceError("io_error", pointer, "cannot read explicit resource") from exc


def _format(path, pointer):
    if path.suffix.lower() not in {".yaml", ".yml", ".json"}:
        raise QueryError("invalid_config", pointer, "resource must be JSON or YAML")
    return "json" if path.suffix.lower() == ".json" else "yaml"


def _resource_path(reference, pointer):
    if "builtin" not in reference:
        return Path(reference["path"])
    path = BUILTINS.get(reference["builtin"])
    if path is None:
        raise QueryError(
            "invalid_config", pointer, "unknown builtin resource",
            {"reason": "unknown_resource"},
        )
    return path


def _resource_content_key(resource):
    path = _resource_path(resource.reference, "/resource")
    return _format(path, "/resource"), resource.sha256


def load_context(value=None, *, base_dir=None):
    if isinstance(value, Context):
        return value
    if isinstance(value, (str, Path)):
        path = Path(os.path.abspath(Path(base_dir or Path.cwd()) / value))
        try:
            text = _read(path, "/context").decode("utf-8")
        except UnicodeDecodeError as exc:
            raise QueryError(
                "invalid_config", "/context", "context must be UTF-8"
            ) from exc
        return load_value(
            text, "context", format=_format(path, "/context"), base_dir=path.parent
        )
    return Context({} if value is None else value, base_dir=base_dir)


def load_resource(reference, kind, *, base_dir=None, pointer="/resource"):
    """Read and validate one catalog, parameter registry, or mapping resource."""
    return _load_resource(reference, kind, base_dir=base_dir, pointer=pointer)


def _load_resource(
    reference, kind, *, base_dir=None, pointer="/resource", prevalidated=False
):
    if kind not in {"catalog", "parameters", "mappings"}:
        raise ValueError(f"unknown resource kind: {kind}")
    try:
        ref = Context({"catalog": reference}, base_dir=base_dir).to_dict()["catalog"]
    except QueryError as exc:
        raise QueryError(
            exc.code,
            pointer + exc.path.removeprefix("/catalog"),
            exc.message,
            dict(exc.context),
        ) from exc
    path = _resource_path(ref, pointer)
    raw = _read(path, pointer)
    digest = hashlib.sha256(raw).hexdigest()
    if "sha256" in ref and digest != ref["sha256"]:
        raise QueryError(
            "invalid_config", pointer + "/sha256", "resource byte digest mismatch"
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise QueryError("invalid_config", pointer, "resource must be UTF-8") from exc
    resource_format = _format(path, pointer)
    use_prevalidated = (
        prevalidated
        and load_prevalidated_resource is not None
        and resource_format == "json"
        and path.parent == _BUILTIN_DIR
    )

    def parse_resource():
        if use_prevalidated:
            return load_prevalidated_resource(text, kind)
        return load_value(text, kind, format=resource_format)

    value = _PARSED_RESOURCES.get_or_create(
        (kind, resource_format, digest, use_prevalidated), parse_resource
    )
    if "version" in ref and value.version != ref["version"]:
        raise QueryError(
            "invalid_config", pointer + "/version", "exact resource version mismatch"
        )
    return LoadedResource(value, freeze(ref), digest, path.parent)


def load_catalog(reference=None, *, base_dir=None):
    """Return the shared Catalog model for exactly one selected resource."""
    return load_resource(
        {"builtin": "reki.catalog"} if reference is None else reference,
        "catalog",
        base_dir=base_dir,
        pointer="/context/catalog",
    ).value
