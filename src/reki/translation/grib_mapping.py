"""Reviewed named GRIB paths over the existing native metadata reader."""

from cedarkit_query import (
    QueryError,
    constrain_query,
    expand_queries,
    intersect_scopes,
    normalize_query,
)
from cedarkit_query.normalize import _contains, duration_seconds, time_seconds

from reki.catalog.model import thaw
from reki.selection.backend import is_concrete
from reki.selection.core import matches

from . import grib
from .common import metadata_error

_RULES = {
    "vertical": "grib.fixed_surfaces",
    "time": "grib.time",
    "statistics": "grib.statistics",
    "member": "grib.member",
    "unit": "common.value_unit",
}


def _covered(row, condition):
    try:
        return constrain_query(row, condition).to_dict() == row
    except QueryError as exc:
        if exc.code == "constraint_conflict":
            return False
        raise


def _error(index, reason, message, *, code="unsupported", field="parameter"):
    raise QueryError(code, f"/queries/{index}/{field}", message, {"reason": reason})


def named_branches(query, index, config, mappings):
    pid = query["parameter"]
    definition = config.parameters[pid]
    context = config.report_context()["source"]
    source = {
        k: context[k] for k in ("dataset", "product", "product_version") if k in context
    }
    provided = [
        thaw(row)
        for row in (config.product or {}).get("provides", ())
        if row.get("parameter") == pid
    ]
    branches = []
    native_conflict = False
    selectors = query.get("native", {}).get("grib", {})
    for (resource, mapping_id), row in mappings.items():
        if row["parameter_id"] != pid:
            continue
        scope = row["applies_to"]
        if (scope.keys() & {"dataset", "product", "product_version"}) - source.keys():
            _error(
                index,
                "missing_context",
                "mapping needs a product identity",
                code="invalid_config",
            )
        if any(
            name in scope and not _contains(scope[name], value, "literal")
            for name, value in source.items()
        ):
            continue
        condition = {"parameter": pid, **row["when"]}
        if "time" in scope:
            bounded = intersect_scopes(condition, {"time": scope["time"]})
            if bounded is None:
                continue
            condition = bounded.to_dict()
        for provision in provided:
            domain = intersect_scopes(condition, provision)
            if domain is None:
                continue
            residual = intersect_scopes(query, domain)
            if residual is None:
                continue
            native = (
                intersect_scopes(
                    {"native": {"grib": row["native"]["match"]}},
                    {"native": {"grib": selectors}},
                )
                if selectors
                else None
            )
            if selectors and native is None:
                native_conflict = True
                continue
            filters = (
                native.native["grib"] if native is not None else row["native"]["match"]
            )
            residual = residual.to_dict()
            if selectors:
                narrowed = {name: thaw(filters[name]) for name in selectors}
                native_conflict |= narrowed != selectors
                residual["native"] = {"grib": narrowed}
            rules = row["native"].get("translate", {})
            template = filters.get("productDefinitionTemplateNumber")
            statistics = definition["fixed_conditions"].get("statistics", {})
            period = statistics.get("period", {}).get("kind")
            if template in {0, 8} and {"member", "member_role"} & query.keys():
                _error(
                    index,
                    "fixed_condition_conflict",
                    "deterministic fields have no member identity",
                    code="constraint_conflict",
                    field="member" if "member" in query else "member_role",
                )
            if (
                any(_RULES.get(duty) != rule["rule"] for duty, rule in rules.items())
                or template not in {0, 1, 8, 11}
                or (template in {1, 11} and config.member_numbering is None)
                or (
                    template in {8, 11}
                    and (
                        statistics.get("operation") not in grib.TIME_OPERATIONS
                        or period not in {"since_initialization", "trailing"}
                    )
                )
                or (
                    template in {0, 1}
                    and statistics.get("operation", "instantaneous") != "instantaneous"
                )
                or statistics.get("over", "time") != "time"
            ):
                _error(
                    index,
                    "translation_unavailable",
                    "named GRIB binding requires a reviewed template, member and statistic path",
                )
            if template in {8, 11}:
                statistical = {
                    "typeOfStatisticalProcessing": grib.TIME_OPERATIONS[
                        statistics["operation"]
                    ],
                }
                if period == "since_initialization":
                    statistical["forecastTime"] = 0
                compatible = intersect_scopes(
                    {"native": {"grib": filters}}, {"native": {"grib": statistical}}
                )
                if compatible is None:
                    native_conflict = True
                    continue
                filters = compatible.native["grib"]
                if selectors:
                    narrowed = {name: thaw(filters[name]) for name in selectors}
                    native_conflict |= narrowed != selectors
                    residual["native"] = {"grib": narrowed}
            declared_unit = rules.get("unit", {}).get("config", {}).get("source_unit")
            if declared_unit is not None:
                _conversion(declared_unit, definition["unit"], pid=pid, index=index)
            basis = [
                {
                    "kind": "mapping",
                    "resource": {"kind": "mappings", "id": resource},
                    "mapping": mapping_id,
                },
                {
                    "kind": "definition",
                    "resource": {
                        "kind": "parameters",
                        "id": next(
                            item["id"]
                            for item in config.definitions
                            if item["role"] == "parameter_registry"
                        ),
                    },
                    "parameter_id": pid,
                },
                *(
                    {"kind": "builtin", "responsibility": duty, "rule": rule["rule"]}
                    for duty, rule in rules.items()
                ),
            ]
            branch = {
                "index": len(branches),
                "backend": "grib2",
                "scope": source,
                "candidate_filter": thaw(filters),
                "residual": residual,
                "basis": basis,
            }
            for previous in branches:
                if (
                    intersect_scopes(previous["residual"], residual) is not None
                    and intersect_scopes(
                        {"native": {"grib": previous["candidate_filter"]}},
                        {"native": {"grib": filters}},
                    )
                    is not None
                ):
                    _error(
                        index,
                        "ambiguous_mapping",
                        "overlapping GRIB mapping branches",
                        code="invalid_config",
                    )
            branches.append(branch)
    if not branches and native_conflict:
        _error(
            index,
            "fixed_condition_conflict",
            "native predicates contradict the named mapping",
            code="constraint_conflict",
            field="native/grib",
        )
    if not any(_covered(query, b["residual"]) for b in branches):
        inputs = [query]
        if config.member_numbering and "member" not in query:
            members = sorted(set(config.member_numbering.values()))
            if "member_role" in query:
                members = [
                    m
                    for m in members
                    if _contains(query["member_role"], config.member_role(m), "literal")
                ]
            if members:
                inputs = [{**query, "member": members}]
        rows = expand_queries(
            inputs, max_expansion=config.execution_defaults["max_expansion"]
        )
        effective = [row.to_dict() for row in rows]
        for row in effective:
            if type(row.get("member")) is int and config.member_numbering:
                row.setdefault("member_role", config.member_role(row["member"]))
        if not all(
            any(_covered(row, b["residual"]) for b in branches) for row in effective
        ):
            if native_conflict:
                _error(
                    index,
                    "fixed_condition_conflict",
                    "explicit native choices exceed the named mapping",
                    code="constraint_conflict",
                    field="native/grib",
                )
            _error(
                index,
                "mapping_coverage_gap",
                "no reviewed GRIB mapping covers the complete query",
            )
    return branches


def expected_cells(query, config):
    """Only explicitly requested cells in the finite catalog domain are known."""
    if "parameter" not in query or config.product is None:
        return None
    domain = config.product.get("expected_domain", ())
    if not domain:
        return None
    domain = [normalize_query(cell).to_dict() for cell in domain]
    rows = expand_queries(
        [query], max_expansion=config.execution_defaults["max_expansion"]
    )
    for row in rows:
        condition = row.to_dict()
        if not is_concrete(condition) or not any(condition == cell for cell in domain):
            return None
    return tuple(row.to_dict() for row in rows)


def _unit(value):
    return {
        "kelvin": "K",
        "Celsius": "degC",
        "degrees_Celsius": "degC",
        "m s-1": "m/s",
        "m s**-1": "m/s",
        "kg m-2": "kg/m2",
        "kg m**-2": "kg/m2",
        "kg kg-1": "kg/kg",
        "kg kg**-1": "kg/kg",
        "J kg-1": "J/kg",
        "J m**-2": "J/m2",
        "m**2 s**-2": "m2/s2",
        "gpm": "Gpm",
        "s**-1": "s-1",
    }.get(value, value)


def _conversion(source, target, *, pid, index=None):
    source, target = _unit(source), _unit(target)
    if source == target:
        return 0.0
    if {source, target} == {"K", "degC"}:
        return -273.15 if source == "K" else 273.15
    if (source, target) == ("kg/m2", "mm") and pid in {
        "cedarkit.rain.since-initialization",
        "cedarkit.rainc.since-initialization",
        "cedarkit.rainnc.since-initialization",
    }:
        return 0.0  # Reviewed water-equivalent precipitation convention.
    if (source, target) == ("m2/s2", "J/kg") and pid in {
        "cedarkit.srh-0-1000",
        "cedarkit.srh-0-3000",
    }:
        return 0.0
    if index is not None:
        _error(
            index, "translation_unavailable", "no reviewed GRIB field unit conversion"
        )
    metadata_error(
        "unsupported_native_encoding", "no reviewed GRIB field unit conversion"
    )


def _observed_units(native, scope, pid, declared):
    decoder = _unit(native.get("units"))
    table = _unit(native.get("parameterUnits"))
    if table != "1" and table == str(native.get("parameterNumber")):
        table = None  # ecCodes repeats the code for a table entry without a unit.
    units = {decoder, table} - {None, "", "unknown", "~"}
    if (scope.get("product"), scope.get("product_version")) != ("orig", "current"):
        return units

    # The reviewed CEMC producer declarations resolve these exact decoder views.
    dataset = scope["dataset"]
    carrier = tuple(
        native.get(key)
        for key in (
            "productDefinitionTemplateNumber",
            "discipline",
            "parameterCategory",
            "parameterNumber",
            "typeOfFirstFixedSurface",
            "typeOfSecondFixedSurface",
        )
    )
    if (
        native.get("edition") != 2
        or native.get("centre") != 38
        or native.get("tablesVersion") != 4
        or native.get("subCentre") != 0
        or native.get("productionStatusOfProcessedData") != 0
    ):
        return units
    if carrier == (0, 0, 1, 0, 106, 106) and (
        pid in {
            "cedarkit.sw",
            "cedarkit.sw-0-10",
            "cedarkit.sw-10-40",
            "cedarkit.sw-40-100",
            "cedarkit.sw-100-200",
        }
        and declared == "m3/m3"
        and native.get("localTablesVersion") in {0, 1}
        and dataset in {"cma_gfs_gmf", "cma_meso_3km", "cma_tym"}
        and (decoder, table) == ("kg/kg", "kg/kg")
    ):
        return {declared}  # The producer overloads SPFH on two soil surfaces.
    if native.get("localTablesVersion") != 0:
        return units
    if carrier == (0, 0, 3, 5, 1, 255) and (
        pid == "cedarkit.zs"
        and declared == "Gpm"
        and dataset in {"cma_gfs_gmf", "cma_meso_1km", "cma_meso_3km", "cma_tym"}
        and (decoder, table) == ("m", "Gpm")
    ):
        return {declared}
    if carrier == (0, 0, 7, 5, 1, 255) and (
        pid == "cedarkit.sweatidx"
        and declared == "1"
        and dataset in {"cma_gfs_gmf", "cma_meso_3km"}
        and (decoder, table) == ("Numeric", "Numeric")
    ):
        return {declared}
    if carrier in {(8, 0, 4, 9, 1, 255), (8, 0, 4, 9, 8, 255)} and (
        pid in {"cedarkit.gsw.since-initialization", "cedarkit.tsw.since-initialization"}
        and declared == "J/m2"
        and dataset == "cma_gfs_gmf"
        and native.get("typeOfStatisticalProcessing") == 1
        and (decoder, table) == ("J/m2", "W m-2")
    ):
        return {declared}  # The base table describes the flux, not its integral.
    if carrier == (0, 0, 7, 8, 103, 103) and (
        pid in {"cedarkit.srh-0-1000", "cedarkit.srh-0-3000"}
        and declared == "m2/s2"
        and dataset in {"cma_meso_1km", "cma_meso_3km"}
        and (decoder, table) == ("m2/s2", "J/kg")
    ):
        return {declared}
    return units


def interpret_named(native, candidates, config, mappings):
    """Interpret target candidates strictly and recheck each complete residual."""
    times, interval = grib.time_fields(native)
    candidates = [
        (qi, branch)
        for qi, branch in candidates
        if matches(times, {k: v for k, v in branch["residual"].items() if k in times})
    ]
    if not candidates:
        return None, (), {}, 0.0
    identity = {**grib.fixed_surfaces(native), **times, "native": {"grib": native}}
    if native["productDefinitionTemplateNumber"] in {1, 11}:
        identity.update(grib.member_fields(native, config))
    selected = []
    for qi, branch in candidates:
        pid = branch["residual"]["parameter"]
        if matches({**identity, "parameter": pid}, branch["residual"]):
            selected.append((qi, branch))
    if not selected:
        return None, (), {}, 0.0
    pids = {branch["residual"]["parameter"] for _, branch in selected}
    if len(pids) != 1:
        metadata_error(
            "inconsistent_native_metadata",
            "record matches multiple business identities",
            parameter_ids=sorted(pids),
        )
    pid = pids.pop()
    definition = config.parameters[pid]
    if interval is not None:
        period = definition["fixed_conditions"]["statistics"]["period"]
        if period["kind"] == "since_initialization":
            correct_window = interval["start"] == times["time"]
        else:
            length = time_seconds(interval["end"]) - time_seconds(interval["start"])
            correct_window = length == duration_seconds(period["duration"])
        if not correct_window:
            metadata_error(
                "fixed_definition_mismatch",
                "the observed statistical interval disagrees with the fixed period",
            )
    source_unit = None
    mapping_ids = set()
    for _, branch in selected:
        basis = branch["basis"][0]
        mapping = mappings[basis["resource"]["id"], basis["mapping"]]
        mapping_ids.add(mapping["id"])
        declared = (
            mapping["native"]
            .get("translate", {})
            .get("unit", {})
            .get("config", {})
            .get("source_unit")
        )
        observed = _observed_units(native, branch["scope"], pid, _unit(declared))
        if declared is not None:
            observed.add(_unit(declared))
        if not observed:
            metadata_error(
                "missing_native_metadata",
                "GRIB field unit is unknown",
                missing_fields=["units"],
            )
        if len(observed) != 1:
            metadata_error(
                "inconsistent_native_metadata",
                "GRIB field unit contradicts the reviewed mapping",
                fields={
                    k: native[k] for k in ("units", "parameterUnits") if k in native
                },
            )
        unit = observed.pop()
        if source_unit is not None and unit != source_unit:
            metadata_error(
                "inconsistent_native_metadata",
                "mappings disagree on the source field unit",
            )
        source_unit = unit
    target = _unit(definition["unit"])
    meta = {
        "parameter_id": pid,
        "parameter_name": definition["name"],
        "unit": target,
        "source_unit": source_unit,
        "mapping_ids": sorted(mapping_ids),
    }
    if "layer" in definition["fixed_conditions"]:
        meta["fixed_layer"] = thaw(definition["fixed_conditions"]["layer"])
    if interval is not None:
        meta["statistical_interval"] = interval
    if "description" in definition:
        meta["description"] = definition["description"]
    return (
        {**identity, "parameter": pid},
        tuple((qi, branch["index"]) for qi, branch in selected),
        meta,
        _conversion(source_unit, target, pid=pid),
    )
