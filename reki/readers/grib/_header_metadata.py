"""Small, decode-free normalisation helpers for GRIB header time metadata."""

from __future__ import annotations

from typing import Any

import pandas as pd


# GRIB2 code table 4.4.  Calendar-based units are deliberately excluded:
# neither an exact ``Timedelta`` nor a reliable fixed number of nanoseconds
# exists for them.
_TIME_UNIT_SECONDS = {
    0: 60,       # minute
    1: 3600,     # hour
    2: 86400,    # day
    10: 3 * 3600,
    11: 6 * 3600,
    12: 12 * 3600,
    13: 1,       # second
}


def _integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _timestamp(date: Any, time: Any) -> pd.Timestamp | None:
    date, time = _integer(date), _integer(time)
    if date is None or time is None:
        return None
    value = pd.to_datetime(f"{date:08d}{time:04d}", format="%Y%m%d%H%M", errors="coerce")
    return None if pd.isna(value) else pd.Timestamp(value)


def timedelta_from_grib(value: Any, unit: Any) -> pd.Timedelta | None:
    """Return an exact duration for a GRIB code-table-4.4 unit/value pair."""
    value, unit = _integer(value), _integer(unit)
    seconds = None if unit is None else _TIME_UNIT_SECONDS.get(unit)
    if value is None or seconds is None:
        return None
    return pd.Timedelta(seconds=value * seconds)


def time_metadata_from_message(message) -> dict[str, pd.Timestamp | pd.Timedelta | None]:
    """Extract public time metadata from an ecCodes handle without decoding values."""
    import eccodes

    def get(key, default=None):
        try:
            return eccodes.codes_get(message, key)
        except (eccodes.KeyValueNotFoundError, eccodes.WrongTypeError):
            return default

    start_time = _timestamp(get("dataDate"), get("dataTime"))

    # ``endStep`` is the lead-time endpoint (and is what the xarray decoder
    # exposes as ``step``).  ``forecastTime`` is retained as a fallback for
    # products where ecCodes cannot provide an end step.
    step = timedelta_from_grib(get("endStep"), get("stepUnits"))
    if step is None:
        step = timedelta_from_grib(
            get("forecastTime"), get("indicatorOfUnitForForecastTime", get("stepUnits")),
        )

    valid_time = _timestamp(get("validityDate"), get("validityTime"))
    if valid_time is None and start_time is not None and step is not None:
        valid_time = start_time + step

    return {
        "start_time": start_time,
        "step": step,
        "valid_time": valid_time,
        "time_range": timedelta_from_grib(
            get("lengthOfTimeRange"), get("indicatorOfUnitOfTimeRange"),
        ),
    }
