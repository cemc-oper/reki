"""The old FieldQuery bridge must preserve every meaningful condition."""

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from cedarkit_query import QueryError
from reki import FieldQuery
from reki.query_adapter import query_from_field_query


START = datetime(2026, 8, 30, tzinfo=timezone.utc)


def convert(query, **kwargs):
    return query_from_field_query("example.grid", query, "cedarkit.t", START,
                                  timedelta(hours=6), **kwargs)


def test_verified_native_parameter_level_window_and_step():
    old = FieldQuery(parameter="t", level_type="pl", level=[850, 500],
                     step_type="accum", time_range="6h",
                     extra={"step": 6, "typeOfFirstFixedSurface": 100})
    result = convert(old, native_parameter="t")
    assert result.to_dict() == {
        "api_version": "cedarkit.query/v1", "domain": "grid", "dataset": "example.grid",
        "parameter": "cedarkit.t", "reference_time": "2026-08-30T00:00:00+00:00",
        "lead_time": "PT21600S", "vertical": {"type": "isobaric", "unit": "hPa", "values": [850, 500]},
        "statistic": {"kind": "accum", "window": "PT21600S"},
    }


def test_surface_and_explicit_member_role():
    old = FieldQuery(level_type="sfc", level=0, step_type="instant", member=0)
    result = convert(old, member_roles={"0": "control"})
    assert result.vertical["type"] == "surface"
    assert result.member == {"id": "0", "role": "control"}
    assert result.statistic == {"kind": "instant"}


@pytest.mark.parametrize("query,options,path", [
    (FieldQuery(parameter="t"), {}, "/field_query/parameter"),
    (FieldQuery(extra={"stepRange": 6}), {}, "/field_query/extra"),
    (FieldQuery(extra={"step": 12}), {}, "/field_query/extra/step"),
    (FieldQuery(level_type="unknown", level=1), {}, "/field_query/level_type"),
    (FieldQuery(level=850), {}, "/field_query/level"),
    (FieldQuery(level_type="pl", level=500, extra={"typeOfFirstFixedSurface": 103}), {},
     "/field_query/extra/typeOfFirstFixedSurface"),
    (FieldQuery(step_type="accum"), {}, "/field_query/time_range"),
    (FieldQuery(step_type="instant", time_range="6h"), {}, "/field_query/time_range"),
    (FieldQuery(time_range="6h"), {}, "/field_query/time_range"),
    (FieldQuery(member=0), {}, "/field_query/member"),
])
def test_unverified_conditions_fail_instead_of_being_dropped(query, options, path):
    with pytest.raises(QueryError) as caught:
        convert(query, **options)
    assert caught.value.path == path


def test_naive_or_subsecond_legacy_time_is_rejected():
    for when in (datetime(2026, 8, 30), pd.Timestamp("2026-08-30T00:00:00.000000001Z")):
        with pytest.raises(QueryError) as caught:
            query_from_field_query("example.grid", FieldQuery(), "cedarkit.t", when, timedelta(hours=6))
        assert caught.value.path == "/query/reference_time"


def test_subsecond_window_is_rejected():
    old = FieldQuery(step_type="mean", time_range=pd.Timedelta(seconds=1, nanoseconds=1))
    with pytest.raises(QueryError) as caught:
        convert(old)
    assert caught.value.path == "/field_query/time_range"


def test_numeric_lead_requires_explicit_unit():
    with pytest.raises(QueryError) as caught:
        query_from_field_query("example.grid", FieldQuery(), "cedarkit.t", START, 6)
    assert caught.value.path == "/query/lead_time"


def test_registry_resolved_t2m_key_and_redundant_first_level_are_checked():
    from reki.readers.grib.config import resolve_parameter

    old = resolve_parameter("cedarkit.t2m").query
    result = query_from_field_query("grid", old, "cedarkit.t2m", START,
                                    timedelta(hours=24), native_parameter="2t")
    assert result.vertical == {"type": "heightAboveGround", "unit": "m", "values": 2}
    with pytest.raises(QueryError) as caught:
        query_from_field_query("grid", old, "cedarkit.t2m", START, timedelta(hours=24))
    assert caught.value.path == "/field_query/parameter"
    with pytest.raises(QueryError) as caught:
        query_from_field_query("grid", old, "cedarkit.unknown", START,
                               timedelta(hours=24), native_parameter="2t")
    assert caught.value.code == "unmapped_parameter"
    wrong = FieldQuery(parameter=old.parameter, level_type=old.level_type, level=old.level,
                       extra={"typeOfFirstFixedSurface": 103, "first_level": 3})
    with pytest.raises(QueryError) as caught:
        query_from_field_query("grid", wrong, "cedarkit.t2m", START,
                               timedelta(hours=24), native_parameter="2t")
    assert caught.value.path == "/field_query/extra/first_level"
