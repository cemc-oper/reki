"""Finite translation helpers; shared declarations remain in cedarkit_query."""

from decimal import Decimal

from cedarkit_query import QueryError, SourceError
from cedarkit_query.normalize import json_number


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
