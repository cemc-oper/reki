from dataclasses import dataclass
from pathlib import Path

import pytest
import pandas as pd

from reki.data_finder import find_local_file


@pytest.fixture
def storage_base():
    return "O:"


@dataclass
class Query:
    data_type: str


@dataclass
class TestCase:
    query: Query
    expected_file_path_template: str


def fill_path(file_path: str, start_time: pd.Timestamp, forecast_time: pd.Timedelta, **kwargs):
    start_time_label = start_time.strftime('%Y%m%d%H')
    start_date_label = start_time.strftime('%Y%m%d')
    year = start_time.strftime('%Y')
    forecast_hour_label = f"{int(forecast_time/pd.Timedelta(hours=1)):03d}"
    return file_path.format(
        start_time_label=start_time_label,
        forecast_hour_label=forecast_hour_label,
        start_date_label=start_date_label,
        year=year,
        **kwargs,
    )


@pytest.mark.parametrize(
    "test_case",
    [
        TestCase(
            Query(data_type="cma_gfs/grib2/orig"),
            expected_file_path_template="{storage_base}/DATA/NAFP/NMC/GRAPES-GFS-GLB/{year}/{start_date_label}/"
                                        "Z_NAFP_C_BABJ_{start_time_label}0000_P_NWPC-GRAPES-GFS-GLB-{forecast_hour_label}00.grib2"
        ),
    ]
)
def test_cma_gfs_grib2_orig(last_two_day, forecast_time_24h, storage_base, test_case):
    data_type = test_case.query.data_type
    file_path = test_case.expected_file_path_template
    start_time = last_two_day
    forecast_time = forecast_time_24h
    expected_data_path = Path(
        fill_path(file_path=file_path, start_time=start_time, forecast_time=forecast_time, storage_base=storage_base)
    )

    data_path = find_local_file(
        data_class="cmadaas",
        data_type=data_type,
        start_time=start_time,
        forecast_time=forecast_time,
        storage_base=storage_base,
    )

    assert data_path is not None
    assert data_path == expected_data_path


@pytest.mark.parametrize(
    "test_case",
    [
        TestCase(
            Query(data_type="cma_meso/grib2/orig"),
            expected_file_path_template="{storage_base}/DATA/NAFP/CEMC/MESO_1KM/ORI/{year}/{start_date_label}/"
                                        "Z_NAFP_C_BABJ_{start_time_label}0000_P_CEMC-CMA-MESO-1KM-ORIG-{forecast_hour_label}00.grb2"
        ),
    ]
)
def test_cma_meso_1km_grib2_orig(last_two_day, forecast_time_24h, storage_base, test_case):
    data_type = test_case.query.data_type
    file_path = test_case.expected_file_path_template
    start_time = last_two_day
    forecast_time = forecast_time_24h
    expected_data_path = Path(
        fill_path(file_path=file_path, start_time=start_time, forecast_time=forecast_time, storage_base=storage_base)
    )

    data_path = find_local_file(
        data_class="cmadaas",
        data_type=data_type,
        start_time=start_time,
        forecast_time=forecast_time,
        storage_base=storage_base,
        debug=True,
    )

    assert data_path is not None
    assert data_path == expected_data_path


@pytest.mark.parametrize(
    "test_case",
    [
        TestCase(
            Query(data_type="cma_tym/grib2/orig"),
            expected_file_path_template="{storage_base}/DATA/NAFP/NMC/GRAPES-TYM/{year}/{start_date_label}/"
                                        "Z_NAFP_C_BABJ_{start_time_label}0000_P_NWPC-GRAPES-TYM-ACWP-{forecast_hour_label}00.grib2"
        ),
    ]
)
def test_cma_tym_grib2_orig(last_two_day, forecast_time_24h, storage_base, test_case):
    data_type = test_case.query.data_type
    file_path = test_case.expected_file_path_template
    start_time = last_two_day
    forecast_time = forecast_time_24h
    expected_data_path = Path(
        fill_path(file_path=file_path, start_time=start_time, forecast_time=forecast_time, storage_base=storage_base)
    )

    data_path = find_local_file(
        data_class="cmadaas",
        data_type=data_type,
        start_time=start_time,
        forecast_time=forecast_time,
        storage_base=storage_base,
        debug=True,
    )

    assert data_path is not None
    assert data_path == expected_data_path
