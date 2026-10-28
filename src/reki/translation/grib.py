"""GRIB2 standard finite paths, independent of ecCodes handles and field values.

WMO/ECMWF tables and the exact supported forms are indexed in I06 evidence.
Local encodings, GRIB1 and complex time ranges are explicit separate paths.
"""

from datetime import datetime, timezone

from cedarkit_query import QueryError, normalize_query, normalize_statistics
from cedarkit_query.normalize import (
    duration_text,
    duration_seconds,
    time_text,
    time_seconds,
    convert_quantity,
)
from reki.catalog.model import thaw
from .common import metadata_error, integer, scaled

TEMPLATES = frozenset({0, 1, 2, 5, 6, 8, 9, 10, 11, 12})
INTERVAL_TEMPLATES = frozenset({8, 9, 10, 11, 12})
UNITS = {0: 60, 1: 3600, 2: 86400, 10: 10800, 11: 21600, 12: 43200, 13: 1}
SURFACES = {
    1: ("surface", None),
    8: ("atmosphere_top", None),
    10: ("entire_atmosphere", None),
    100: ("pressure", "Pa"),
    101: ("mean_sea_level", None),
    102: ("height_above_sea", "m"),
    103: ("height_above_ground", "m"),
    106: ("depth_below_land", "m"),
}


def applicability(meta):
    if integer(meta, "edition") != 2:
        metadata_error(
            "unsupported_native_encoding",
            "GRIB1 requires its own confirmed interpretation path",
        )
    integer(meta, "centre")
    integer(meta, "subCentre")
    integer(meta, "tablesVersion", maximum=254)
    integer(meta, "localTablesVersion", maximum=254)
    if meta["tablesVersion"] != 4 or meta["localTablesVersion"] != 0:
        metadata_error(
            "unsupported_native_encoding",
            "this initial finite profile covers master table 4 with no local-table reinterpretation",
            fields={
                "tablesVersion": meta["tablesVersion"],
                "localTablesVersion": meta["localTablesVersion"],
            },
        )
    template = integer(meta, "productDefinitionTemplateNumber", maximum=65534)
    if template not in TEMPLATES:
        metadata_error(
            "unsupported_native_encoding",
            "product definition template has no registered finite path",
            fields={"productDefinitionTemplateNumber": template},
        )
    return template


def fixed_surfaces(meta, *, vertical_definition=None):
    def endpoint(which):
        code = integer(
            meta,
            "typeOf" + which + "FixedSurface",
            maximum=254,
            reason="invalid_vertical_metadata",
        )
        if code == 105:
            if not vertical_definition:
                raise QueryError(
                    "invalid_config",
                    "/context",
                    "hybrid levels need an exact vertical definition",
                    {"reason": "missing_context"},
                )
            value = scaled(
                meta,
                "scaleFactorOf" + which + "FixedSurface",
                "scaledValueOf" + which + "FixedSurface",
            )
            if type(value) is not int:
                metadata_error(
                    "invalid_vertical_metadata",
                    "model level identifier must be integral",
                )
            return {"type": "model_level", "value": value}
        if code not in SURFACES:
            metadata_error(
                "unsupported_native_encoding",
                "fixed surface code needs a separately confirmed path",
                fields={"surface_type": code},
            )
        kind, unit = SURFACES[code]
        if unit is None:
            return {"type": kind}
        return {
            "type": kind,
            "value": scaled(
                meta,
                "scaleFactorOf" + which + "FixedSurface",
                "scaledValueOf" + which + "FixedSurface",
            ),
            "unit": unit,
        }

    first = endpoint("First")
    second_type = integer(
        meta,
        "typeOfSecondFixedSurface",
        maximum=255,
        reason="invalid_vertical_metadata",
    )
    if second_type == 255:
        result = {"level_type": first["type"]}
        if "value" in first:
            result["level"] = first["value"]
            if "unit" in first:
                result["level_unit"] = first["unit"]
        return normalize_query(result).to_dict()
    second = endpoint("Second")
    if first["type"] != second["type"] or "value" not in first or "value" not in second:
        metadata_error(
            "unsupported_native_encoding",
            "mixed/native named boundary ordering needs a confirmed finite path",
        )
    if first["type"] == "model_level":
        metadata_error(
            "unsupported_native_encoding",
            "model level intervals do not imply physical ordering",
        )
    # bottom/top are physical: deeper depth and higher pressure form bottom.
    descending = first["type"] in {"pressure", "depth_below_land"}
    ends = sorted([first, second], key=lambda p: p["value"], reverse=descending)
    try:
        return normalize_query({"layer": {"bottom": ends[0], "top": ends[1]}}).to_dict()
    except QueryError as exc:
        from cedarkit_query import SourceError

        raise SourceError(
            "metadata_interpretation_failed",
            "",
            "fixed surfaces do not form a valid interval",
            {"reason": "invalid_vertical_metadata"},
        ) from exc


def _stamp(meta, keys):
    values = [integer(meta, k, reason="invalid_time_metadata") for k in keys]
    if values[-1] == 60:
        metadata_error(
            "unsupported_native_encoding",
            "leap-second timestamps need a separately registered representation",
        )
    try:
        dt = datetime(*values, tzinfo=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    except (ValueError, OverflowError) as exc:
        from cedarkit_query import SourceError

        raise SourceError(
            "metadata_interpretation_failed",
            "",
            "invalid native calendar fields",
            {
                "reason": "invalid_time_metadata",
                "native_fields": dict(zip(keys, values)),
            },
        ) from exc


def _seconds(meta, unit_key, value_key):
    unit = integer(meta, unit_key, maximum=255, reason="invalid_time_metadata")
    if unit not in UNITS:
        metadata_error(
            "unsupported_native_encoding",
            "calendar or unregistered native time unit",
            fields={unit_key: unit},
        )
    value = integer(
        meta,
        value_key,
        minimum=-2147483647 if value_key == "forecastTime" else 0,
        reason="invalid_time_metadata",
    )
    if value < 0:
        metadata_error(
            "unsupported_native_encoding",
            "negative forecast offsets need a separate finite path",
        )
    return value * UNITS[unit]


def time_fields(meta):
    template = applicability(meta)
    if integer(
        meta, "significanceOfReferenceTime", maximum=255, reason="invalid_time_metadata"
    ) not in {0, 1}:
        metadata_error(
            "unsupported_native_encoding",
            "reference time meaning needs a confirmed product path",
        )
    origin = _stamp(meta, ["year", "month", "day", "hour", "minute", "second"])
    start = time_seconds(origin) + _seconds(
        meta, "indicatorOfUnitOfTimeRange", "forecastTime"
    )
    interval = None
    end = start
    if template in INTERVAL_TEMPLATES:
        if (
            integer(
                meta,
                "numberOfTimeRange",
                minimum=1,
                reason="invalid_statistics_metadata",
            )
            != 1
        ):
            metadata_error(
                "unsupported_native_encoding",
                "multiple statistical time descriptors are not flattened",
            )
        if (
            integer(
                meta, "typeOfTimeIncrement", maximum=255, reason="invalid_time_metadata"
            )
            != 2
        ):
            metadata_error(
                "unsupported_native_encoding",
                "time-increment structure needs a separate path",
            )
        encoded_end = _stamp(
            meta,
            [
                "yearOfEndOfOverallTimeInterval",
                "monthOfEndOfOverallTimeInterval",
                "dayOfEndOfOverallTimeInterval",
                "hourOfEndOfOverallTimeInterval",
                "minuteOfEndOfOverallTimeInterval",
                "secondOfEndOfOverallTimeInterval",
            ],
        )
        end = time_seconds(encoded_end)
        length = _seconds(meta, "indicatorOfUnitForTimeRange", "lengthOfTimeRange")
        if end < start:
            metadata_error(
                "invalid_time_metadata", "statistical interval ends before its start"
            )
        if end - start != length:
            metadata_error(
                "inconsistent_native_metadata",
                "encoded interval bounds and length disagree",
            )
        interval = {"start": time_text(start), "end": time_text(end)}
    result = normalize_query(
        {
            "time": origin,
            "step": duration_text(end - time_seconds(origin)),
            "valid_time": time_text(end),
        }
    ).to_dict()
    return result, interval


def member(meta, configuration, *, numbering=None):
    template = applicability(meta)
    if template not in {1, 11}:
        return {}  # Deterministic and ensemble products are not individual members.
    number = integer(
        meta, "perturbationNumber", maximum=254, reason="invalid_member_metadata"
    )
    kind = integer(
        meta, "typeOfEnsembleForecast", maximum=254, reason="invalid_member_metadata"
    )
    if kind not in {0, 1, 2, 3, 5, 6}:
        metadata_error(
            "unsupported_native_encoding",
            "native member attribute needs a confirmed joint-numbering path",
            fields={"typeOfEnsembleForecast": kind},
        )
    if numbering is None:
        raise QueryError(
            "invalid_config",
            "/context",
            "member numbering has no exact product contract",
            {"reason": "missing_context"},
        )
    if (kind, number) not in numbering:
        metadata_error(
            "unmapped_native_value",
            "member attribute/number has no canonical entry",
            fields={"typeOfEnsembleForecast": kind, "perturbationNumber": number},
        )
    canonical = numbering[(kind, number)]
    if type(canonical) is not int or canonical < 0:
        raise QueryError(
            "invalid_config",
            "/context",
            "invalid canonical member in internal numbering contract",
        )
    native_role = "control" if kind in {0, 1, 5} else "perturbation"
    role = configuration.member_role(canonical)
    if role is not None and role != native_role:
        metadata_error(
            "inconsistent_native_metadata",
            "native member attribute contradicts effective role mapping",
        )
    return {"member": canonical, "member_role": role or native_role}


def check_period(stats, identity, interval):
    operation = stats.get("operation", "instantaneous")
    if operation == "instantaneous":
        if interval is not None:
            metadata_error(
                "fixed_definition_mismatch",
                "time interval conflicts with instantaneous definition",
            )
        return
    if interval is None:
        metadata_error(
            "fixed_definition_mismatch",
            "time statistic requires its actual native interval",
        )
    period = stats.get("period")
    if period is None:
        raise QueryError(
            "invalid_config",
            "/statistics/period",
            "concrete time statistic needs a period",
            {"reason": "missing_context"},
        )
    start, end = time_seconds(interval["start"]), time_seconds(interval["end"])
    expected = (
        end - duration_seconds(period["duration"])
        if period["kind"] == "trailing"
        else time_seconds(identity["time"])
    )
    if start != expected:
        metadata_error(
            "fixed_definition_mismatch",
            "native statistical interval conflicts with the fixed period",
        )


def statistics(
    meta, fixed, identity, interval, *, resources=None, product=None, object_unit=None
):
    """Verify an existing product; never reconstruct a statistic from member values."""
    template = applicability(meta)
    stats = thaw(fixed.get("statistics", {}))
    if not stats:
        if template in {0, 1}:
            return {"over": "time", "operation": "instantaneous"}
        raise QueryError(
            "invalid_config",
            "/statistics",
            "statistical product needs its effective definition",
            {"reason": "missing_context"},
        )
    stats = normalize_statistics(stats, complete=True)
    time_stats = stats
    if stats["over"] == "ensemble":
        if product is None or resources is None:
            raise QueryError(
                "invalid_config",
                "/statistics",
                "ensemble product needs exact population and object context",
                {"reason": "missing_context"},
            )
        parameter = resources.parameter(stats["of"]["parameter_id"])
        time_stats = parameter["fixed_conditions"].get("statistics")
        if time_stats is None:
            raise QueryError(
                "invalid_config",
                "/statistics/of",
                "ensemble object time statistic needs an explicit definition",
                {"reason": "missing_context"},
            )
        normalize_statistics(time_stats, complete=True)
        if stats["population"].get("ref") not in {
            p["id"] for p in product["populations"]
        }:
            raise QueryError(
                "invalid_config",
                "/statistics/population",
                "population is not declared by this product",
                {"reason": "missing_context"},
            )
        op = stats["operation"]
        if template in {2, 12}:
            code = integer(
                meta,
                "derivedForecast",
                maximum=254,
                reason="invalid_statistics_metadata",
            )
            allowed = {0: "mean", 8: "minimum", 9: "maximum"}
            if code not in allowed:
                metadata_error(
                    "unsupported_native_encoding",
                    "derived ensemble operation needs a separate finite path",
                    fields={"derivedForecast": code},
                )
            if op != allowed[code]:
                metadata_error(
                    "fixed_definition_mismatch",
                    "derived forecast disagrees with the fixed operation",
                )
            if code == 0 and stats["method"].get("weighting") != "equal":
                metadata_error(
                    "fixed_definition_mismatch",
                    "unweighted native mean contradicts fixed weighting",
                )
        elif template in {6, 10}:
            quantile = (
                integer(
                    meta,
                    "percentileValue",
                    maximum=100,
                    reason="invalid_statistics_metadata",
                )
                / 100
            )
            if op != "quantile" or stats["quantile"] != quantile:
                metadata_error(
                    "fixed_definition_mismatch",
                    "native percentile disagrees with the fixed quantile",
                )
        elif template in {5, 9}:
            if op != "probability":
                metadata_error(
                    "fixed_definition_mismatch",
                    "probability template contradicts fixed operation",
                )
            code = integer(
                meta,
                "probabilityType",
                maximum=254,
                reason="invalid_statistics_metadata",
            )
            operators = {
                0: ("lt", "lower"),
                1: ("gt", "upper"),
                3: ("gt", "lower"),
                4: ("lt", "upper"),
            }
            if code not in {*operators, 2}:
                metadata_error(
                    "unsupported_native_encoding",
                    "probability event needs a separate finite path",
                    fields={"probabilityType": code},
                )
            if object_unit is None:
                raise QueryError(
                    "invalid_config",
                    "/statistics/event",
                    "native threshold unit requires object-unit evidence",
                    {"reason": "missing_context"},
                )
            event = stats["event"]

            def limit(side):
                return scaled(
                    meta,
                    "scaleFactorOf" + side.title() + "Limit",
                    "scaledValueOf" + side.title() + "Limit",
                    reason="invalid_statistics_metadata",
                    signed=True,
                )

            if code == 2:
                lower, upper = limit("lower"), limit("upper")
                if lower >= upper:
                    metadata_error(
                        "invalid_statistics_metadata",
                        "native probability interval has invalid ordering",
                    )
                compatible = (
                    event["operator"] == "between"
                    and event["lower"]["inclusive"]
                    and not event["upper"]["inclusive"]
                )
                if compatible:
                    compatible = all(
                        convert_quantity(v, object_unit, event[side]["unit"])
                        == event[side]["value"]
                        for side, v in (("lower", lower), ("upper", upper))
                    )
            else:
                operator, side = operators[code]
                threshold = limit(side)
                compatible = (
                    event["operator"] == operator
                    and convert_quantity(
                        threshold, object_unit, event["threshold"]["unit"]
                    )
                    == event["threshold"]["value"]
                )
            if not compatible:
                metadata_error(
                    "fixed_definition_mismatch",
                    "native probability event contradicts the fixed event",
                )

        else:
            metadata_error(
                "fixed_definition_mismatch",
                "ensemble definition does not match the native template family",
            )
    elif template not in {0, 1, 8, 11}:
        metadata_error(
            "fixed_definition_mismatch",
            "native ensemble product conflicts with a time-only definition",
        )
    if template in INTERVAL_TEMPLATES:
        code = integer(
            meta,
            "typeOfStatisticalProcessing",
            maximum=254,
            reason="invalid_statistics_metadata",
        )
        operation = {0: "mean", 1: "accumulation", 2: "maximum", 3: "minimum"}.get(code)
        if operation is None:
            metadata_error(
                "unsupported_native_encoding",
                "statistical processing code needs a separate path",
                fields={"typeOfStatisticalProcessing": code},
            )
        if operation != time_stats["operation"]:
            metadata_error(
                "fixed_definition_mismatch",
                "native time operation contradicts fixed definition",
            )
    check_period(time_stats, identity, interval)
    return stats
