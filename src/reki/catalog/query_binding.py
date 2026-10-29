"""Pure source/context construction for I05. No field discovery or execution."""

from pathlib import Path
from string import Formatter

from cedarkit_query import (
    Query,
    analyze_product_mappings,
    QueryError,
    Request,
    intersect_scopes,
    validate_product,
    validate_resource_set,
)

from .loader import load_context, load_resource
from .model import SourceConfiguration, freeze
from .current import current_registration

# Existing, explicitly identified CEMC datasets; never infer from a path/prefix.
_CEMC = frozenset(
    {
        "cma_gfs_gmf",
        "cma_meso_3km",
        "cma_meso_1km",
        "cma_tym",
        "cma_geps",
        "cma_reps",
        "cma_gfs_gmf_cmadaas",
        "cma_gfs_gmf_analysis_cmadaas",
        "cma_meso_3km_forecast_cmadaas",
        "cma_meso_3km_analysis_cmadaas",
        "cma_meso_1km_forecast_cmadaas",
        "cma_meso_1km_analysis_cmadaas",
        "cma_tym_forecast_cmadaas",
        "cma_tym_analysis_cmadaas",
        "cma_geps_control_cmadaas",
        "cma_geps_perturbation_cmadaas",
        "cma_reps_control_cmadaas",
        "cma_reps_perturbation_cmadaas",
    }
)


def _missing(path, message):
    raise QueryError("invalid_config", path, message, {"reason": "missing_context"})


def _layout(value):
    """Validate deployment-owned, root-relative ordered templates, without discovery.

    This is an internal locator registration, not a new public Query/resource schema.
    Formatter slots are already used by reki's controlled query locator. Rendering,
    time/step interpretation and filesystem containment remain I05 responsibilities.
    """
    if not isinstance(value, (list, tuple)) or not value:
        _missing(
            "/source/root", "local source needs registered ordered layout templates"
        )
    for item in value:
        if (
            not isinstance(item, str)
            or not item
            or Path(item).is_absolute()
            or "\\" in item
        ):
            raise QueryError(
                "invalid_config", "/source/root", "layout must be root-relative"
            )
        if any(p in {"", ".", ".."} for p in item.split("/")):
            raise QueryError("invalid_config", "/source/root", "unsafe layout path")
        try:
            fields = list(Formatter().parse(item))
        except ValueError as exc:
            raise QueryError(
                "invalid_config", "/source/root", "malformed layout template"
            ) from exc
        for _, field, spec, conversion in fields:
            if field is not None and (
                field
                not in {
                    "start_time_label",
                    "forecast_hour",
                    "forecast_hour_label",
                    "date_label",
                    "year",
                    "member_3digit",
                }
                or spec
                or conversion
            ):
                raise QueryError(
                    "unsupported", "/source/root", "unsupported locator template field"
                )
    return tuple(value)


def plan_source_binding(
    source,
    *,
    context=None,
    product=None,
    product_version=None,
    source_id=None,
    base_dir=None,
    defaults=None,
    local_layouts=None,
    interface_contracts=(),
    client=None,
):
    """Freeze selected resources and exact product/source facts for later execution.

    defaults contains registered catalog/parameter_registry/mappings references,
    not auto-discovered settings. Product/version must be explicit or registered
    for the selected builtin dataset. Native files receive no business defaults.
    CMADaaS interface_contracts is an exact registry supplied by I06, never inferred.
    local_layouts keys are (dataset, product, business-version, source-binding-id).
    """
    source = Request.from_dict(
        {"api_version": "cedarkit.request/v1", "source": source, "queries": [{}]},
        base_dir=base_dir,
    ).to_dict()["source"]
    ctx = load_context(context, base_dir=base_dir).to_dict()
    default = load_context(defaults, base_dir=base_dir).to_dict()
    if set(default) - {"catalog", "parameter_registry", "mappings"}:
        raise QueryError(
            "invalid_config",
            "/defaults",
            "only builtin resource references may be registered",
        )
    if client is not None and (source["kind"] != "cmadaas" or "config" in source):
        raise QueryError(
            "invalid_config",
            "/source",
            "client conflicts with this source configuration",
        )
    if source["kind"] == "cmadaas" and "config" not in source and client is None:
        _missing("/source/config", "CMADaaS needs config or an external client")
    origins = {}
    definitions = []
    catref = ctx.get("catalog", default.get("catalog", {"builtin": "reki.catalog"}))
    catalog = load_resource(catref, "catalog", pointer="/context/catalog")
    definitions.append(catalog.snapshot("catalog"))
    origins["catalog"] = "context" if "catalog" in ctx else "builtin"
    data = catalog.value.to_dict()
    dataset = None
    if "dataset" in source:
        candidates = [
            d
            for d in data["datasets"]
            if source["dataset"] == d["id"] or source["dataset"] in d.get("aliases", [])
        ]
        if len(candidates) != 1:
            _missing("/source/dataset", "dataset is absent from the selected catalog")
        dataset = candidates[0]
        source["dataset"] = dataset["id"]
        registration = current_registration(catalog, dataset["id"])
        if registration is not None:
            if product is None:
                product = registration["product"]
            if product_version is None:
                product_version = registration["product_version"]
            default.setdefault("parameter_registry", registration["parameter_registry"])
            if local_layouts is None:
                local_layouts = {
                    (
                        dataset["id"],
                        registration["product"],
                        registration["product_version"],
                        "cmadaas-disk",
                    ): registration["local_layout"]
                }
            origins["product_selection"] = "builtin.current-business"
            origins["provision_scope"] = (
                "limited-supported-pairs; complete_product_coverage=false"
            )
        if product is None or product_version is None:
            _missing(
                "/source/dataset", "exact product and business version are required"
            )
    elif any(v is not None for v in (product, product_version, source_id)):
        _missing("/source/dataset", "product/source binding requires a dataset")

    pref = ctx.get("parameter_registry", default.get("parameter_registry"))
    parameters = None
    if pref is not None:
        parameters = load_resource(
            pref, "parameters", pointer="/context/parameter_registry"
        )
        definitions.append(parameters.snapshot("parameter_registry"))
        origins["parameter_registry"] = (
            "context" if "parameter_registry" in ctx else "builtin"
        )
    mapping_resources = []
    for backend in ("grib2", "cmadaas"):
        choices = [
            (ctx.get("mappings", {}), "context", None),
            ((dataset or {}).get("mappings", {}), "dataset", catalog.base_dir),
            (default.get("mappings", {}), "builtin", None),
        ]
        for refs, origin, base in choices:
            if backend not in refs:
                continue
            loaded = load_resource(
                refs[backend],
                "mappings",
                base_dir=base,
                pointer="/context/mappings/" + backend,
            )
            if loaded.value.backend != backend:
                raise QueryError(
                    "invalid_config",
                    "/context/mappings/" + backend,
                    "mapping resource contains another backend",
                )
            mapping_resources.append(loaded.value.to_dict())
            definitions.append(loaded.snapshot("mappings", backend=backend))
            origins["mappings." + backend] = origin
            break
    if parameters is None and (dataset is not None or mapping_resources):
        _missing(
            "/context/parameter_registry",
            "selected product/mappings need a parameter registry",
        )
    resources = (
        validate_resource_set(parameters.value.to_dict(), mapping_resources, data)
        if parameters is not None
        else None
    )
    execution = {"completeness": "available", "max_expansion": 10000}
    for key in execution:
        origins["execution." + key] = "library"
    roles = {}
    for values, origin in [((dataset or {}), "dataset"), (ctx, "context")]:
        roles.update(values.get("member_roles", {}))
        for key, value in values.get("execution", {}).items():
            execution[key] = value
            origins["execution." + key] = origin
        for member in values.get("member_roles", {}):
            origins["member_roles." + member] = origin
    selected = None
    layout = None
    applicability = []
    product_coverage = ()
    scope = Query(ctx.get("scope", {}))
    if dataset is not None:
        selected = validate_product(resources, dataset["id"], product, product_version)
        # Configuration scopes are bounds; do not enumerate the product domain.
        scope = intersect_scopes(scope, selected["scope"])
        if scope is None:
            raise QueryError(
                "constraint_conflict",
                "/context/scope",
                "context and product scopes are disjoint",
            )
        analysis = analyze_product_mappings(
            resources, dataset["id"], product, product_version, scope=scope
        )
        applicability = analysis["rows"]
        product_coverage = analysis["provides"]
        failures = [
            item
            for item in product_coverage
            if item["static_status"] in {"missing", "partial"}
        ]
        if failures:
            first = failures[0]
            raise QueryError(
                "invalid_config",
                "/context/mappings/" + first["backend"],
                "selected mapping resource does not cover declared product choices",
                {
                    "reason": "missing_context",
                    "resource_id": first["resource_id"],
                    "parameter_id": first["parameter_id"],
                    "provided_index": first["provided_index"],
                    "static_status": first["static_status"],
                    "coverage_reason": first["reason"],
                    "uncovered_example": first["uncovered_example"],
                },
            )
        bindings = [
            s
            for s in selected["sources"]
            if s["kind"] == source["kind"]
            and (source_id is None or s["id"] == source_id)
        ]
        if len(bindings) != 1:
            _missing(
                "/source",
                "exactly one source binding is required; select source_id explicitly",
            )
        binding = bindings[0]
        origins["source_binding"] = binding["id"]
        if source["kind"] == "cmadaas":
            contract = binding["interface_contract"]
            if (contract["id"], contract["version"]) not in interface_contracts:
                _missing(
                    "/source/interface_contract",
                    "exact CMADaaS interface contract is not registered",
                )
        if source["kind"] == "local":
            key = (dataset["id"], product, product_version, binding["id"])
            layout = _layout((local_layouts or {}).get(key))
    cemc = source.get("dataset") in _CEMC
    origins["member_roles.default"] = "CEMC" if cemc else "unknown"
    if selected is not None:
        for provided in selected["provides"]:
            names = provided.get("parameter", ())
            for name in (names,) if isinstance(names, str) else names:
                fixed = resources.parameter(name).get("fixed_conditions", {})
                if "member" in fixed and "member_role" in fixed:
                    member = fixed["member"]
                    role = roles.get(
                        str(member),
                        ("control" if member == 0 else "perturbation")
                        if cemc
                        else None,
                    )
                    if role is not None and role != fixed["member_role"]:
                        raise QueryError(
                            "constraint_conflict",
                            "/context/member_roles",
                            "effective member role conflicts with a provided parameter definition",
                        )
    return SourceConfiguration(
        freeze(source),
        resources,
        selected,
        scope,
        freeze(execution),
        freeze(roles),
        cemc,
        tuple(freeze(d) for d in definitions),
        freeze(origins),
        layout,
        tuple(applicability),
        tuple(product_coverage),
    )
