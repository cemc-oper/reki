from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytest
import pandas as pd

from reki.data_finder import find_local_file


@dataclass
class Query:
    data_type: str
    number: int


@dataclass
class TestCase:
    query: Query
    expected_file_path_template: str


def fill_path(file_path: str, start_time: pd.Timestamp, forecast_time: pd.Timedelta, **kwargs):
    start_time_label = start_time.strftime('%Y%m%d%H')
    forecast_hour_label = f"{int(forecast_time/pd.Timedelta(hours=1)):03d}"
    return file_path.format(
        start_time_label=start_time_label,
        forecast_hour_label=forecast_hour_label,
        **kwargs,
    )


@pytest.mark.parametrize(
    "test_case",
    [
        TestCase(
            Query(data_type="cma_reps/grib2/orig", number=0),
            expected_file_path_template="/g3/COMMONDATA/OPER/CEMC/REPS/Prod-grib/{start_time_label}/grib2/"
                                        "mef.gra.000.{start_time_label}{forecast_hour_label}.grb2"
        ),
        TestCase(
            Query(data_type="cma_reps/grib2/orig", number=14),
            expected_file_path_template="/g3/COMMONDATA/OPER/CEMC/REPS/Prod-grib/{start_time_label}/grib2/"
                                        "mef.gra.014.{start_time_label}{forecast_hour_label}.grb2"
        ),
    ]
)
def test_grib2(last_two_day, forecast_time_24h, test_case):
    data_type = test_case.query.data_type
    file_path = test_case.expected_file_path_template
    start_time = last_two_day + pd.Timedelta(hours=6)
    forecast_time = forecast_time_24h
    expected_data_path = Path(fill_path(file_path=file_path, start_time=start_time, forecast_time=forecast_time))

    data_path = find_local_file(
        data_type=data_type,
        start_time=start_time,
        forecast_time=forecast_time,
        number=test_case.query.number,
    )

    assert data_path is not None
    assert data_path == expected_data_path
