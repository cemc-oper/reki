"""Pure source/context construction for I05. No field discovery or execution."""

from pathlib import Path
from string import Formatter

from cedarkit_query import (
    Query,
    QueryError,
    Request,
    intersect_scopes,
    prepare_queries,
    validate_resource_set,
)
from cedarkit_query.resources import effective_parameters

from .current import current_registration
from .loader import load_context, load_resource
from .model import SourceConfiguration, freeze


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
                    "beijing_date_label",
                    "beijing_year",
                    "next_beijing_date_label",
                    "next_beijing_year",
                }
                or spec
                or conversion
            ):
                raise QueryError(
                    "unsupported", "/source/root", "unsupported locator template field"
                )
    return tuple(value)


def _bind_resources(ctx, dataset, catalog, kind, origins, definitions):
    parameter_ref = ctx.get("parameter_registry", dataset.get("parameter_registry"))
    references = {
        backend: (ref, origin)
        for owner, origin in ((dataset, "dataset"), (ctx, "context"))
        for backend, ref in owner.get("mappings", {}).items()
    }
    products = [
        product
        for product in dataset.get("products", ())
        if any(source["kind"] == kind for source in product["sources"])
    ]
    if parameter_ref is None and not references and not products:
        return None, (), None
    if parameter_ref is None:
        _missing(
            "/context/parameter_registry", "the selected resources require parameters"
        )
    if len(products) > 1:
        _missing("/source/dataset", "source must bind one unambiguous product version")
    if not products and references:
        _missing("/source/dataset", "mapping resources require a catalog product")
    origin = "context" if "parameter_registry" in ctx else "dataset"
    parameters = load_resource(
        parameter_ref,
        "parameters",
        base_dir=catalog.base_dir,
        pointer="/context/parameter_registry",
    )
    origins["parameter_registry"] = origin
    definitions.append(freeze(parameters.snapshot("parameter_registry")))
    if not products:
        return freeze(effective_parameters(parameters.value)), (), None

    mappings = []
    for backend, (ref, origin) in sorted(references.items()):
        loaded = load_resource(
            ref,
            "mappings",
            base_dir=catalog.base_dir,
            pointer="/context/mappings/" + backend,
        )
        if loaded.value.backend != backend:
            raise QueryError(
                "invalid_config",
                "/context/mappings/" + backend,
                "mapping resource backend mismatch",
            )
        definitions.append(freeze(loaded.snapshot("mappings", backend=backend)))
        origins["mappings." + backend] = origin
        mappings.append(loaded.value)
    effective = validate_resource_set(
        parameters.value,
        mappings,
        catalog.value,
        dataset["id"],
    )
    return freeze(effective), tuple(mappings), freeze(products[0])


def plan_source_binding(source, *, context=None, base_dir=None, client=None):
    """Resolve dataset aliases and file layouts before any discovery."""
    source = Request.from_dict(
        {"api_version": "cedarkit.request/v1", "source": source, "queries": [{}]},
        base_dir=base_dir,
    ).to_dict()["source"]
    ctx = load_context(context, base_dir=base_dir).to_dict()
    if client is not None and (source["kind"] != "cmadaas" or "config" in source):
        raise QueryError("invalid_config", "/source", "client conflicts with source")
    if source["kind"] == "cmadaas" and "config" not in source and client is None:
        _missing("/source/config", "CMADaaS needs config or an external client")

    catalog = load_resource(
        ctx.get("catalog", {"builtin": "reki.catalog"}),
        "catalog",
        pointer="/context/catalog",
    )
    dataset = {}
    if "dataset" in source:
        dataset = next(
            (
                row
                for row in catalog.value.to_dict()["datasets"]
                if source["dataset"] in (row["id"], *row.get("aliases", ()))
            ),
            None,
        )
        if dataset is None:
            _missing("/source/dataset", "dataset is absent from the selected catalog")
        source["dataset"] = dataset["id"]

    execution = {"completeness": "available", "max_expansion": 10000}
    roles = {}
    origins = {"catalog": "context" if "catalog" in ctx else "builtin"}
    definitions = [freeze(catalog.snapshot("catalog"))]
    parameters, mappings, product = _bind_resources(
        ctx,
        dataset,
        catalog,
        source["kind"],
        origins,
        definitions,
    )
    registration = current_registration(catalog, dataset.get("id"), product=product) or {}
    layout, fallback_layout = None, ()
    if source["kind"] == "local":
        layout = _layout(dataset.get("local_layout") or registration.get("local_layout"))
        if registration.get("local_fallback_layout"):
            fallback_layout = _layout(registration["local_fallback_layout"])
    scope = Query(ctx.get("scope", {}))
    if product is not None:
        scope = intersect_scopes(scope, product["scope"])
        if scope is None:
            raise QueryError(
                "constraint_conflict",
                "/context/scope",
                "context and product scopes are disjoint",
            )
    if "parameter" in scope.to_dict() and parameters is not None:
        bound = prepare_queries([scope], parameters)
        if len(bound) != 1:
            raise QueryError(
                "invalid_config",
                "/context/scope/parameter",
                "parameter scope must bind one fixed business identity",
            )
        scope = bound[0]
    for name in execution:
        origins[f"execution.{name}"] = "library"
    for values, origin in ((dataset, "dataset"), (ctx, "context")):
        roles.update(values.get("member_roles", {}))
        for name in values.get("member_roles", {}):
            origins[f"member_roles.{name}"] = origin
        for name, value in values.get("execution", {}).items():
            execution[name] = value
            origins[f"execution.{name}"] = origin
    numbering = registration.get("member_numbering")
    member_numbering = (
        None
        if numbering is None
        else freeze(
            {
                (row["typeOfEnsembleForecast"], row["perturbationNumber"]): row[
                    "member"
                ]
                for row in numbering
            }
        )
    )
    cemc = bool(registration)
    origins["member_roles.default"] = "CEMC" if cemc else "unknown"
    return SourceConfiguration(
        freeze(source),
        scope,
        freeze(execution),
        freeze(roles),
        cemc,
        tuple(definitions),
        freeze(origins),
        layout,
        member_numbering,
        parameters,
        mappings,
        product,
        fallback_layout,
    )
