import pandas as pd
import pytest

from reki import FieldQuery
from reki.readers.grib.reader import GribReader


def test_field_query_freezes_sequences_normalizes_timedelta_and_merges():
    levels = [850, 500]
    first = FieldQuery(parameter="t", level=levels, time_range="6h", extra={"stepRange": 6})
    levels.append(300)
    merged = first.merge(FieldQuery(level_type="pl", level=None, extra={"stepRange": 12, "edition": None}))
    assert first.level == (850, 500)
    assert first.time_range == pd.Timedelta(hours=6)
    assert merged.level_type == "pl"
    assert merged.level == (850, 500)
    assert merged.extra == {"stepRange": 12}


def test_field_query_rejects_standard_extra_conflict():
    with pytest.raises(TypeError, match="conflicts"):
        FieldQuery(extra={"level": 850})


def test_grib_sel_has_one_query_path_and_is_immutable():
    reader = GribReader(None, "unused.grib")
    selected = reader.sel(parameter="t", level=[850, 500], stepRange=6)
    selected_from_query = reader.sel(FieldQuery(parameter="t", level=[850, 500], extra={"stepRange": 6}))
    assert reader.filters == {}
    assert selected.filters == selected_from_query.filters
    assert selected.sel(level=None, stepRange=None).filters == selected.filters
    with pytest.raises(TypeError, match="cannot be mixed"):
        reader.sel(FieldQuery(parameter="t"), level=850)
