from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytest
import pandas as pd

from reki.data_finder import find_local_file


@dataclass
class Query:
    data_type: str
    obs_timedelta: Optional[pd.Timedelta] = None


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
            Query(data_type="cma_meso_3km/grib2/orig"),
            expected_file_path_template="/g3/COMMONDATA/OPER/CEMC/MESO_3KM/Prod-grib/{start_time_label}/ORIG/"
                                        "rmf.hgra.{start_time_label}{forecast_hour_label}.grb2"
        ),
        TestCase(
            Query(data_type="cma_meso_3km/grib2/modelvar"),
            expected_file_path_template="/g3/COMMONDATA/OPER/CEMC/MESO_3KM/Prod-grib/{start_time_label}/MODELVAR/"
                                        "modelvar{start_time_label}{forecast_hour_label}.grb2"
        ),
    ]
)
def test_grib2(last_two_day, forecast_time_24h, test_case):
    data_type = test_case.query.data_type
    file_path = test_case.expected_file_path_template
    start_time = last_two_day
    forecast_time = forecast_time_24h
    expected_data_path = Path(fill_path(file_path=file_path, start_time=start_time, forecast_time=forecast_time))

    data_path = find_local_file(
        data_type=data_type,
        start_time=start_time,
        forecast_time=forecast_time,
    )

    assert data_path is not None
    assert data_path == expected_data_path


@pytest.mark.parametrize(
    "test_case",
    [
        TestCase(
            Query(data_type="cma_meso_3km/bin/modelvar"),
            expected_file_path_template="/g3/COMMONDATA/OPER/CEMC/MESO_3KM/Fcst-main/{start_time_label}/"
                                        "modelvar{start_time_label}{forecast_hour_label}00"
        ),
        TestCase(
            Query(data_type="cma_meso_3km/bin/modelvar_ctl"),
            expected_file_path_template="/g3/COMMONDATA/OPER/CEMC/MESO_3KM/Fcst-main/{start_time_label}/"
                                        "modelvar.ctl_{start_time_label}00000"
        ),
        TestCase(
            Query(data_type="cma_meso_3km/bin/postvar"),
            expected_file_path_template="/g3/COMMONDATA/OPER/CEMC/MESO_3KM/Fcst-main/{start_time_label}/"
                                        "postvar{start_time_label}{forecast_hour_label}00"
        ),
        TestCase(
            Query(data_type="cma_meso_3km/bin/postvar_ctl"),
            expected_file_path_template="/g3/COMMONDATA/OPER/CEMC/MESO_3KM/Fcst-main/{start_time_label}/"
                                        "postvar.ctl_{start_time_label}00000"
        ),
    ]
)
def test_bin(last_two_day, forecast_time_12h, test_case):
    data_type = test_case.query.data_type
    file_path = test_case.expected_file_path_template
    start_time = last_two_day
    forecast_time = forecast_time_12h
    expected_data_path = Path(fill_path(file_path=file_path, start_time=start_time, forecast_time=forecast_time))

    data_path = find_local_file(
        data_type=data_type,
        start_time=start_time,
        forecast_time=forecast_time,
    )

    assert data_path is not None
    assert data_path == expected_data_path
