from pathlib import Path

import pandas as pd
import pytest

from reki.sources.file_pattern import FilePatternSource


def test_file_pattern_renders_only_the_frozen_time_variables():
    source = FilePatternSource(
        "/data/{start_time_label}",
        "gmf.{start_time_label}{forecast_hour_label}.grb2",
        start_time="2026082700",
        forecast_time="24h",
    )
    assert source.resolve_path() == Path("/data/2026082700/gmf.2026082700024.grb2")


@pytest.mark.parametrize("template", ["{start_time:%Y}", "{unknown}", "{start_time_label.__class__}"])
def test_file_pattern_rejects_expressions_and_unknown_variables(template):
    source = FilePatternSource(template, "file.grb2", start_time="2026082700")
    with pytest.raises(ValueError):
        source.resolve_path()


def test_file_pattern_requires_whole_hour_forecast_time():
    source = FilePatternSource("/data", "file.grb2", start_time=pd.Timestamp("2026-08-27"), forecast_time="90m")
    with pytest.raises(ValueError, match="integer"):
        source.resolve_path()
