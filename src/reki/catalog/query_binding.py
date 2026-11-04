"""Pure source/context construction for I05. No field discovery or execution."""

from pathlib import Path
from string import Formatter

from cedarkit_query import Query, QueryError, Request

from .loader import load_context, load_resource
from .model import SourceConfiguration, freeze
from .current import current_registration


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
                }
                or spec
                or conversion
            ):
                raise QueryError(
                    "unsupported", "/source/root", "unsupported locator template field"
                )
    return tuple(value)


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
    registration = None
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
        registration = current_registration(catalog, dataset["id"])
    layout = None
    if source["kind"] == "local":
        layout = _layout(
            (registration or {}).get("local_layout") or dataset.get("local_layout")
        )

    execution = {"completeness": "available", "max_expansion": 10000}
    roles = {}
    origins = {"catalog": "context" if "catalog" in ctx else "builtin"}
    for name in execution:
        origins[f"execution.{name}"] = "library"
    for values, origin in ((dataset, "dataset"), (ctx, "context")):
        roles.update(values.get("member_roles", {}))
        for name in values.get("member_roles", {}):
            origins[f"member_roles.{name}"] = origin
        for name, value in values.get("execution", {}).items():
            execution[name] = value
            origins[f"execution.{name}"] = origin
    numbering = (registration or {}).get("member_numbering")
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
    cemc = registration is not None
    origins["member_roles.default"] = "CEMC" if cemc else "unknown"
    return SourceConfiguration(
        freeze(source),
        Query(ctx.get("scope", {})),
        freeze(execution),
        freeze(roles),
        cemc,
        (freeze(catalog.snapshot("catalog")),),
        freeze(origins),
        layout,
        member_numbering,
    )
