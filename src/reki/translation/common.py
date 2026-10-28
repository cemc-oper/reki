"""Finite translation helpers; shared declarations remain in cedarkit_query."""

from decimal import Decimal
from dataclasses import dataclass

from cedarkit_query import QueryError, SourceError, validate_rule
from cedarkit_query.normalize import unit_info, unit_name, json_number


def metadata_error(reason, message, *, fields=None, **context):
    raise SourceError(
        "metadata_interpretation_failed",
        "",
        message,
        {"reason": reason, **({"native_fields": fields} if fields else {}), **context},
    )


def required(metadata, key):
    missing_codes = {
        "typeOfFirstFixedSurface",
        "typeOfEnsembleForecast",
        "perturbationNumber",
        "significanceOfReferenceTime",
        "indicatorOfUnitOfTimeRange",
        "indicatorOfUnitForTimeRange",
        "typeOfTimeIncrement",
        "typeOfStatisticalProcessing",
        "probabilityType",
        "percentileValue",
        "tablesVersion",
        "localTablesVersion",
    }
    if (
        key not in metadata
        or metadata[key] is None
        or (key in missing_codes and metadata[key] == 255)
    ):
        metadata_error(
            "missing_native_metadata",
            "required native metadata is absent",
            missing_fields=[key],
        )
    return metadata[key]


def integer(
    metadata, key, *, minimum=0, maximum=None, reason="inconsistent_native_metadata"
):
    value = required(metadata, key)
    if (
        type(value) is not int
        or value < minimum
        or (maximum is not None and value > maximum)
    ):
        metadata_error(
            reason,
            "native integer is outside its supported structural range",
            fields={key: value},
        )
    return value


def unsupported(message, **context):
    raise QueryError(
        "unsupported",
        "/queries",
        message,
        {"reason": "translation_unavailable", **context},
    )


@dataclass(frozen=True)
class UnitRequirement:
    source: str
    target: str
    scale: Decimal
    offset: Decimal


def value_unit(response_unit, target_unit, rule=None, *, quantity_kind=None):
    """common.value_unit: no values are read or converted by this rule."""
    rule = validate_rule(
        rule or {"rule": "common.value_unit"}, backend="grib2", responsibility="unit"
    )
    declared = rule.get("config", {}).get("source_unit")
    if declared is not None and response_unit:
        if unit_info(declared) != unit_info(response_unit):
            metadata_error(
                "inconsistent_native_metadata",
                "response unit conflicts with the mapping source_unit",
                fields={"response_unit": response_unit, "source_unit": declared},
            )
    source = response_unit or declared
    if not source:
        metadata_error(
            "missing_native_metadata",
            "source value unit has no response or definition evidence",
            missing_fields=["source_unit"],
        )
    if not target_unit:
        raise QueryError(
            "invalid_config",
            "/unit",
            "business target unit is missing",
            {"reason": "missing_context"},
        )
    sd, sf, so = unit_info(source)
    td, tf, to = unit_info(target_unit)
    if sd != td:
        unsupported(
            "source and business units are incompatible",
            source_unit=source,
            target_unit=target_unit,
        )
    if so != to and quantity_kind != "absolute_temperature":
        unsupported(
            "affine value conversion requires explicit absolute-temperature evidence"
        )
    return UnitRequirement(
        unit_name(source), unit_name(target_unit), sf / tf, (so - to) / tf
    )


def scaled(
    metadata, factor_key, value_key, *, reason="invalid_vertical_metadata", signed=False
):
    factor = integer(metadata, factor_key, minimum=-127, maximum=127, reason=reason)
    value = integer(
        metadata,
        value_key,
        minimum=-2147483646 if signed else 0,
        maximum=2147483646 if signed else 4294967294,
        reason=reason,
    )
    # Missing integer sentinels are handled by the adapter before this pure rule.
    try:
        return json_number(Decimal(value) * Decimal(10) ** -factor)
    except (ValueError, ArithmeticError, QueryError) as exc:
        raise SourceError(
            "metadata_interpretation_failed",
            "",
            "scaled native quantity is not representable",
            {"reason": reason, "native_fields": {factor_key: factor, value_key: value}},
        ) from exc


def software_origin(profile):
    from importlib.metadata import version, PackageNotFoundError

    try:
        release = version("reki")
    except PackageNotFoundError:
        release = "uninstalled-source"
    return f"reki-distribution={release};profile={profile}"
