"""Explicit, byte-pinned local resources. No environment discovery or fallback."""

import hashlib
import os
from pathlib import Path
from types import MappingProxyType

from cedarkit_query import Context, QueryError, SourceError, load_value

from .model import LoadedResource, freeze

# Resource defaults are activated only by an explicitly registered dataset.
BUILTINS = MappingProxyType(
    {
        "reki.catalog": Path(__file__).with_name("builtin") / "catalog-v1.json",
        "reki.parameters.cma-gfs.current": Path(__file__).with_name("builtin")
        / "current-gfs-parameters.json",
        "reki.mappings.cma-gfs.current": Path(__file__).with_name("builtin")
        / "current-gfs-mappings.json",
        "reki.parameters.cma-meso-3km.current": Path(__file__).with_name("builtin")
        / "current-meso3-parameters.json",
        "reki.mappings.cma-meso-3km.current": Path(__file__).with_name("builtin")
        / "current-meso3-mappings.json",
        "reki.parameters.cma-meso-1km.current": Path(__file__).with_name("builtin")
        / "current-meso1-parameters.json",
        "reki.mappings.cma-meso-1km.current": Path(__file__).with_name("builtin")
        / "current-meso1-mappings.json",
        "reki.parameters.cma-tym.current": Path(__file__).with_name("builtin")
        / "current-tym-parameters.json",
        "reki.mappings.cma-tym.current": Path(__file__).with_name("builtin")
        / "current-tym-mappings.json",
        "reki.parameters.cma-geps.current": Path(__file__).with_name("builtin")
        / "current-geps-parameters.json",
        "reki.mappings.cma-geps.current": Path(__file__).with_name("builtin")
        / "current-geps-mappings.json",
        "reki.parameters.cma-reps.current": Path(__file__).with_name("builtin")
        / "current-reps-parameters.json",
        "reki.mappings.cma-reps.current": Path(__file__).with_name("builtin")
        / "current-reps-mappings.json",
    }
)


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
    # The shared context validates references; do not maintain another ref schema.
    key = {
        "parameters": "parameter_registry",
        "catalog": "catalog",
        "mappings": "mappings",
    }[kind]
    wrapped = {key: {"grib2": reference} if kind == "mappings" else reference}
    checked = Context(wrapped, base_dir=base_dir).to_dict()[key]
    ref = checked["grib2"] if kind == "mappings" else checked
    if "builtin" in ref:
        path = BUILTINS.get(ref["builtin"])
        if path is None:
            raise QueryError(
                "invalid_config",
                pointer,
                "unknown builtin resource",
                {"reason": "unknown_resource"},
            )
    else:
        path = Path(ref["path"])
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
    value = load_value(text, kind, format=_format(path, pointer))
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
