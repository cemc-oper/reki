"""GRIB2 standard finite paths, independent of ecCodes handles and field values.

WMO/ECMWF tables and the exact supported forms are indexed in I06 evidence.
Local encodings, GRIB1 and complex time ranges are explicit separate paths.
"""

from datetime import datetime, timezone

from cedarkit_query import QueryError, normalize_query
from cedarkit_query.normalize import (
    duration_text,
    time_text,
    time_seconds,
)
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
    # The confirmed mixed named-boundary path keeps a layer, not a fabricated
    # numeric height or the distinct code-10 entire-atmosphere level.
    if {first["type"], second["type"]} == {"surface", "atmosphere_top"}:
        return normalize_query(
            {
                "layer": {
                    "bottom": {"type": "surface"},
                    "top": {"type": "atmosphere_top"},
                }
            }
        ).to_dict()
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


def _seconds(meta, unit_key, value_key, *, signed_start=False):
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
    if value < 0 and not signed_start:
        metadata_error(
            "unsupported_native_encoding",
            "negative forecast offsets need a separate finite path",
        )
    return value * UNITS[unit]


def time_fields(meta):
    template = integer(meta, "productDefinitionTemplateNumber", maximum=65534)
    if template not in TEMPLATES:
        metadata_error(
            "unsupported_native_encoding",
            "time projection for this template is unavailable",
        )
    if integer(
        meta, "significanceOfReferenceTime", maximum=255, reason="invalid_time_metadata"
    ) not in {0, 1}:
        metadata_error(
            "unsupported_native_encoding",
            "reference time meaning needs a confirmed product path",
        )
    origin = _stamp(meta, ["year", "month", "day", "hour", "minute", "second"])
    reference = time_seconds(origin)
    start = reference + _seconds(
        meta,
        "indicatorOfUnitOfTimeRange",
        "forecastTime",
        signed_start=template in INTERVAL_TEMPLATES,
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
    if end < reference:
        metadata_error(
            "unsupported_native_encoding",
            "result before the reference time needs a separate canonical time path",
        )
    result = normalize_query(
        {
            "time": origin,
            "step": duration_text(end - reference),
            "valid_time": time_text(end),
        }
    ).to_dict()
    return result, interval


TIME_OPERATIONS = {"mean": 0, "accumulation": 1, "maximum": 2, "minimum": 3}


def member_fields(meta, configuration):
    kind = integer(
        meta, "typeOfEnsembleForecast", maximum=254, reason="invalid_member_metadata"
    )
    number = integer(
        meta, "perturbationNumber", maximum=254, reason="invalid_member_metadata"
    )
    member = configuration.member_numbering.get((kind, number))
    if member is None:
        metadata_error(
            "unmapped_native_value",
            "member has no reviewed numbering",
            fields={"typeOfEnsembleForecast": kind, "perturbationNumber": number},
        )
    role = configuration.member_role(member)
    expected = "control" if kind in {0, 1, 5} else "perturbation"
    if role != expected:
        metadata_error(
            "inconsistent_native_metadata",
            "member role contradicts the native code",
            fields={"typeOfEnsembleForecast": kind, "perturbationNumber": number},
        )
    return {"member": member, "member_role": role}
