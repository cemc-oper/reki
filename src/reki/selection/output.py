"""Assemble actual fields into an in-memory Dataset, without re-running queries."""

from decimal import Decimal
import numpy as np
import xarray as xr

from cedarkit_query import QueryError
from cedarkit_query.normalize import (
    unit_info,
    unit_name,
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


def _number(value):
    text = format(Decimal(str(value)), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _layer_name(name, layer):
    bottom, top = layer["bottom"], layer["top"]

    def boundary(v):
        return v["type"] + (
            "_" + _number(v["value"]) + v.get("unit", "") if "value" in v else ""
        )

    if bottom["type"] == top["type"] and "value" in bottom and "value" in top:
        return (
            f"{name}__layer__{bottom['type']}__bottom_{_number(bottom['value'])}{bottom.get('unit', '')}"
            f"__top_{_number(top['value'])}{top.get('unit', '')}"
        )
    return f"{name}__layer__bottom_{boundary(bottom)}__top_{boundary(top)}"


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


def _variable(field):
    identity = field.identity.to_dict()
    meta = thaw(field.metadata)
    parameter = identity.get("parameter")
    # Native selection is allowed without fabricated parameter IDs or names.
    if parameter is not None:
        if meta.get("parameter_id") != parameter or not meta.get("parameter_name"):
            _error("unsupported", "backend lacks exact canonical parameter metadata")
    name = meta.get("parameter_name")
    layer = identity.get("layer")
    fixed_layer = meta.get("fixed_conditions", {}).get("layer")
    if layer and layer != fixed_layer and name:
        name = _layer_name(name, layer)
    semantics = {
        k: v
        for k, v in identity.items()
        if k
        not in {*_AXES, "valid_time", "member_role", "level", "level_unit", "native"}
    }
    if parameter is None:
        # Unregistered native fields have no proven shared business variable.
        # Preserve native distinctions rather than merging different quantities.
        semantics["native"] = identity.get("native", {})
    if "statistics" in meta:
        semantics["statistics"] = meta["statistics"]
    # Numeric level varies along a compatible coordinate; layer remains variable identity.
    return key(semantics), name, identity, meta


def _attrs(identity, meta):
    attrs = {}
    for src, target in (
        ("parameter_id", "cedarkit_parameter_id"),
        ("parameter_name", "cedarkit_parameter_name"),
        ("description", "long_name"),
        ("standard_name", "standard_name"),
    ):
        if src in meta:
            if (
                src in {"parameter_id", "parameter_name"}
                and "parameter" not in identity
            ):
                continue
            attrs[target] = meta[src]
    if "layer" in identity:
        for side, endpoint in identity["layer"].items():
            for k, v in endpoint.items():
                attrs[f"layer_{side}_{'value' if k == 'value' else k}"] = v
    elif identity.get("level_type") not in _VERTICAL and "level_type" in identity:
        attrs["level_type"] = identity["level_type"]
    target = meta.get("unit")
    if target:
        attrs["units"] = unit_name(target)
    return attrs


def _values(field, meta):
    source, target = meta.get("source_unit"), meta.get("unit")
    if not source or not target:
        _error(
            "unsupported", "source and business value units require explicit evidence"
        )
    sd, sf, so = unit_info(source)
    td, tf, to = unit_info(target)
    if sd != td:
        _error(
            "unsupported",
            "incompatible value units",
            source_unit=source,
            target_unit=target,
        )
    # Affine temperature conversion needs explicit absolute-temperature semantics.
    if so != to and meta.get("quantity_kind") != "absolute_temperature":
        _error("unsupported", "affine conversion needs absolute-temperature evidence")
    array = field._reference.load()
    if not isinstance(array, xr.DataArray) or not array.dims:
        _error("unsupported", "backend must return a spatial DataArray")
    if set(array.dims) & {*_AXES, *_VERTICAL, "valid_time", "member_role"}:
        _error("unsupported", "backend values must contain spatial axes only")
    array = array.load().copy(deep=True)
    # Avoid xarray inheriting unreviewed per-record attrs or stale native names.
    grid_mapping = array.attrs.get("grid_mapping")
    if grid_mapping is not None and grid_mapping not in array.coords:
        _error(
            "incompatible_grid", "projection reference lacks its coordinate definition"
        )
    attrs = {} if grid_mapping is None else {"grid_mapping": grid_mapping}
    array.attrs = {}
    if (sf, so) != (tf, to):
        array = array * float(sf / tf) + float((so - to) / tf)
    array.attrs = attrs
    return array


def assemble(fields, report, rename, configuration):
    groups, names, positions, grids, vertical, roles = {}, {}, set(), [], {}, {}
    for field in fields:
        semantic, name, identity, meta = _variable(field)
        group = groups.setdefault(
            semantic, dict(name=name, rows=[], attrs=_attrs(identity, meta))
        )
        if group["name"] != name or group["attrs"] != _attrs(identity, meta):
            _error(
                "duplicate_field", "inconsistent canonical metadata within one variable"
            )
        coords = _coordinates(identity)
        pos = (semantic, key({k: str(v) for k, v in coords.items()}))
        if pos in positions:
            _error(
                "duplicate_field", "different records occupy the same business position"
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
                    "different business variables have the same default name",
                    name=name,
                )
            names[name] = semantic

    if isinstance(rename, str):
        if len(groups) != 1:
            _error(
                "multiple_variables",
                "string rename requires exactly one business variable",
            )
        targets = {g: rename for g in groups}
    elif rename is None or isinstance(rename, dict):
        rename = {} if rename is None else rename
        missing_names = _missing_names(report, configuration)
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
            array = _values(field, meta)
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


def _missing_names(report, configuration):
    # Missing variables have no actual Field; only resource-backed canonical names
    # can be recognized. Parameter IDs must not be treated as business names.
    names = set()
    if configuration.resources is None:
        return names
    for missing in report.overall["missing"]:
        identity = thaw(missing["selection"])
        if "parameter" not in identity:
            continue
        p = configuration.resources.parameter(identity["parameter"])
        name = p["name"]
        layer = identity.get("layer")
        if layer and layer != p["fixed_conditions"].get("layer"):
            name = _layer_name(name, layer)
        names.add(name)
    return names
