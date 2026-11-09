"""Assemble actual fields into an in-memory Dataset, without re-running queries."""

import numpy as np
import xarray as xr

from cedarkit_query import QueryError
from cedarkit_query.normalize import (
    time_seconds,
    duration_seconds,
)
from reki.catalog.model import thaw
from .core import key

_VERTICAL = (
    "pressure",
    "height_above_ground",
    "height_above_sea",
    "depth_below_land",
    "model_level",
)
_AXES = ("time", "step", "member")


def _error(code, message, **context):
    raise QueryError(
        code, "", message, {"operation": "to_xarray", "stage": "assembly", **context}
    )


def _nanoseconds(value, time=False):
    n = (time_seconds(value) if time else duration_seconds(value)) * 1_000_000_000
    if n != n.to_integral_value() or not -(2**63) < n < 2**63:
        _error("unsupported", "time outside lossless nanosecond representation")
    return np.datetime64(int(n), "ns") if time else np.timedelta64(int(n), "ns")


def _coordinates(identity):
    coords = {}
    for axis in _AXES:
        if axis in identity:
            coords[axis] = (
                _nanoseconds(identity[axis], time=axis == "time")
                if axis in {"time", "step"}
                else identity[axis]
            )
    kind = identity.get("level_type")
    if kind in _VERTICAL and "layer" not in identity:
        coords[kind] = identity["level"]
    return coords


def _business_name(identity, name, fixed_layer):
    layer = identity.get("layer")
    if layer is None or layer == fixed_layer:
        return name
    bottom, top = layer["bottom"], layer["top"]

    def value(point):
        return f"{point.get('value', '')}{point.get('unit', '')}"

    if bottom["type"] == top["type"]:
        return (
            f"{name}__layer__{bottom['type']}__bottom_{value(bottom)}__top_{value(top)}"
        )
    endpoints = [
        f"{side}_{point['type']}" + (f"_{value(point)}" if "value" in point else "")
        for side, point in (("bottom", bottom), ("top", top))
    ]
    return name + "__layer__" + "__".join(endpoints)


def _variable(field):
    identity = field.identity.to_dict()
    meta = thaw(field.metadata)
    if "parameter_id" in meta:
        semantic = {
            "parameter": meta["parameter_id"],
            "vertical": identity.get("level_type"),
        }
        name = _business_name(identity, meta["parameter_name"], meta.get("fixed_layer"))
        if "layer" in identity:
            semantic["layer"] = identity["layer"]
        return key(semantic), name, identity, meta
    return key(meta["native_variable"]), meta["native_name"], identity, meta


def _attrs(identity, meta):
    if "parameter_id" in meta:
        attrs = {
            "cedarkit_parameter_id": meta["parameter_id"],
            "cedarkit_parameter_name": meta["parameter_name"],
            "units": meta["unit"],
        }
        if "description" in meta:
            attrs["long_name"] = meta["description"]
        if "code_table" in meta:
            attrs["code_table"] = meta["code_table"]
    else:
        attrs = {f"GRIB_{k}": v for k, v in meta["native_variable"].items()}
        units = meta.get("native_fields", {}).get("units")
        if units is not None:
            attrs["units"] = units
    if "layer" in identity:
        for side, endpoint in identity["layer"].items():
            for k, v in endpoint.items():
                attrs[f"layer_{side}_{k}"] = v
    elif identity.get("level_type") not in _VERTICAL and "level_type" in identity:
        attrs["level_type"] = identity["level_type"]
    return attrs


def _values(field):
    field._owner._ensure_open()
    array = field._reference.load()
    if not isinstance(array, xr.DataArray) or not array.dims:
        _error("unsupported", "backend must return a spatial DataArray")
    if set(array.dims) & {*_AXES, *_VERTICAL, "valid_time", "member_role"}:
        _error("unsupported", "backend values must contain spatial axes only")
    array = array.load().copy(deep=True)
    field._owner._ensure_open()
    # Avoid xarray inheriting unreviewed per-record attrs or stale native names.
    grid_mapping = array.attrs.get("grid_mapping")
    if grid_mapping is not None and grid_mapping not in array.coords:
        _error(
            "incompatible_grid", "projection reference lacks its coordinate definition"
        )
    attrs = {} if grid_mapping is None else {"grid_mapping": grid_mapping}
    array.attrs = {}
    array.attrs = attrs
    return array


def assemble(fields, report, rename, *, parameters=None):
    groups, names, positions, grids, vertical, roles = {}, {}, set(), [], {}, {}
    for field in fields:
        semantic, name, identity, meta = _variable(field)
        group = groups.setdefault(
            semantic, dict(name=name, rows=[], attrs=_attrs(identity, meta))
        )
        if group["name"] != name or group["attrs"] != _attrs(identity, meta):
            _error(
                "duplicate_field", "inconsistent native metadata within one variable"
            )
        coords = _coordinates(identity)
        pos = (semantic, key({k: str(v) for k, v in coords.items()}))
        if pos in positions:
            _error(
                "duplicate_field", "different records occupy the same native position"
            )
        positions.add(pos)
        if not field._reference.grid:
            _error("incompatible_grid", "grid definition is not established")
        grids.append(field._reference.grid)
        if grids[-1] != grids[0]:
            _error(
                "incompatible_grid",
                "grid definitions differ; no interpolation is performed",
            )
        kind = identity.get("level_type")
        if kind in _VERTICAL and "layer" not in identity:
            definition = meta.get("vertical_definition")
            if not definition or (kind in vertical and vertical[kind] != definition):
                _error(
                    "incompatible_grid",
                    "vertical coordinate definitions are missing or incompatible",
                )
            vertical[kind] = definition
        if "member" in identity:
            member, role = identity["member"], identity.get("member_role")
            if member in roles and roles[member] != role:
                _error("duplicate_field", "member roles conflict")
            roles[member] = role
        group["rows"].append((field, identity, meta, coords))
        if name is not None:
            if name in names and names[name] != semantic:
                _error(
                    "multiple_variables",
                    "different native variables have the same default name",
                    name=name,
                )
            names[name] = semantic

    if isinstance(rename, str):
        if len(groups) != 1:
            _error(
                "multiple_variables",
                "string rename requires exactly one native variable",
            )
        targets = {g: rename for g in groups}
    elif rename is None or isinstance(rename, dict):
        rename = {} if rename is None else rename
        missing_names = set()
        if rename and parameters:
            for missing in report.overall["missing"]:
                selection = missing["selection"]
                definition = parameters.get(selection.get("parameter"))
                if definition is not None:
                    missing_names.add(
                        _business_name(
                            selection,
                            definition["name"],
                            definition["fixed_conditions"].get("layer"),
                        )
                    )
        for source in rename:
            if source not in names and source not in missing_names:
                _error(
                    "invalid_query",
                    "rename contains an unknown source name",
                    name=source,
                )
        targets = {g: rename.get(v["name"], v["name"]) for g, v in groups.items()}
    else:
        _error("invalid_query", "rename must be a string or a name mapping")
    if any(not isinstance(n, str) or not n.strip() for n in targets.values()):
        _error("unsupported", "native output needs a reliable name or string rename")
    if len(set(targets.values())) != len(targets):
        _error("multiple_variables", "rename targets collide")

    variables = {}
    spatial = None
    for semantic, group in groups.items():
        arrays = []
        # Every field in a variable must use the same applicable axes.
        applicable = set(group["rows"][0][3])
        projection_attrs = None
        for field, identity, meta, coords in group["rows"]:
            if set(coords) != applicable:
                _error("duplicate_field", "variable mixes incompatible applicable axes")
            array = _values(field)
            if projection_attrs is None:
                projection_attrs = dict(array.attrs)
            elif projection_attrs != array.attrs:
                _error("incompatible_grid", "projection references differ")
            snapshot = (array.dims, {k: v for k, v in array.coords.items()})
            if spatial is None:
                spatial = snapshot
            else:
                dims, coordinates = spatial
                if (
                    array.dims != dims
                    or set(array.coords) != set(coordinates)
                    or any(
                        not array.coords[k].identical(v) for k, v in coordinates.items()
                    )
                ):
                    _error(
                        "incompatible_grid",
                        "spatial coordinates or projection metadata differ",
                    )
            axes = [a for a in (*_AXES, *_VERTICAL) if a in coords]
            for axis in reversed(axes):
                array = array.expand_dims({axis: [coords[axis]]})
            arrays.append(array)
        # Only observed coordinate domains form the rectangular output.
        if applicable:
            array = xr.merge(
                [a.to_dataset(name="__value") for a in arrays],
                compat="no_conflicts",
                join="outer",
                combine_attrs="drop",
            )["__value"]
        else:
            array = arrays[0]
        array.attrs = {**projection_attrs, **group["attrs"]}
        variables[targets[semantic]] = array
    reserved = set(_AXES) | set(_VERTICAL) | {"valid_time", "member_role"}
    if spatial is not None:
        reserved |= set(spatial[0]) | set(spatial[1])
    if reserved & set(variables):
        _error(
            "multiple_variables",
            "data variable name collides with a coordinate or dimension",
        )
    ds = xr.Dataset(variables)
    if spatial is not None:
        for name, coordinate in spatial[1].items():
            ds[name].attrs = dict(coordinate.attrs)
    for axis in (*_AXES, *_VERTICAL):
        if axis in ds.dims:
            ds = ds.sortby(axis, ascending=axis != "pressure")
    for name in ds.data_vars:
        a = ds[name]
        ds[name] = a.transpose(
            *[d for d in (*_AXES, *_VERTICAL) if d in a.dims],
            *[d for d in a.dims if d not in {*_AXES, *_VERTICAL}],
        )
    for axis in ("time", "valid_time"):
        if axis in ds.coords:
            ds[axis].attrs["timezone"] = "UTC"
    if "time" in ds.coords and "step" in ds.coords:
        # Add in integer space to detect overflow instead of wrapping to another date.
        times = ds.time.values.astype("datetime64[ns]").astype("int64")
        steps = ds.step.values.astype("timedelta64[ns]").astype("int64")
        summed = times.astype(object)[:, None] + steps.astype(object)[None, :]
        if any(not -(2**63) < v < 2**63 for v in summed.flat):
            _error(
                "unsupported", "valid_time outside lossless nanosecond representation"
            )
        ds = ds.assign_coords(
            valid_time=(
                ("time", "step"),
                np.array(summed, dtype="int64").astype("datetime64[ns]"),
            )
        )
        ds.valid_time.attrs["timezone"] = "UTC"
    if "member" in ds.coords and roles and all(v is not None for v in roles.values()):
        ds = ds.assign_coords(
            member_role=("member", [roles[int(v)] for v in ds.member.values])
        )
    for axis in _VERTICAL:
        if axis in ds.coords:
            ds[axis].attrs["level_type"] = axis
            if axis != "model_level":
                ds[axis].attrs["units"] = "hPa" if axis == "pressure" else "m"
    for axis, unit in (("latitude", "degrees_north"), ("longitude", "degrees_east")):
        if axis in ds.coords:
            ds[axis].attrs["units"] = unit
    # Presence/translation reports do not claim value quality or conversion checks.
    snapshot = report.to_json()
    ds.attrs["cedarkit_query_report"] = snapshot
    for array in ds.data_vars.values():
        array.attrs["cedarkit_query_report"] = snapshot
    return ds.load().copy(deep=True)
