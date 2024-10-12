import pytest
import pandas as pd
from pathlib import Path

from reki.data_finder import find_local_file


def fill_path(file_path: str, start_time: pd.Timestamp, forecast_time: pd.Timedelta):
    start_time_label = start_time.strftime('%Y%m%d%H')
    forecast_hour_label = f"{int(forecast_time/pd.Timedelta(hours=1)):03d}"
    return file_path.format(
        start_time_label=start_time_label,
        forecast_hour_label=forecast_hour_label,
    )


@pytest.mark.parametrize(
    "grib2_type,grib2_path",
    [
        ("orig", "/g3/COMMONDATA/OPER/CEMC/GFS_GMF/Prod-grib/{start_time_label}/ORIG/"
                 "gmf.gra.{start_time_label}{forecast_hour_label}.grb2"),
        ("ne", "/g3/COMMONDATA/OPER/CEMC/GFS_GMF/Prod-grib/{start_time_label}/CMACAST/"
                 "ne_gmf.gra.{start_time_label}{forecast_hour_label}.grb2"),
        ("modelvar", "/g3/COMMONDATA/OPER/CEMC/GFS_GMF/Prod-grib/{start_time_label}/MODELVAR/"
                 "modelvar{start_time_label}{forecast_hour_label}.grb2"),
    ]
)
def test_grib2(cma_gfs_system_name, last_two_day, forecast_time_24h, grib2_type, grib2_path):
    data_type = f"{cma_gfs_system_name}/grib2/{grib2_type}"
    start_time = last_two_day
    forecast_time = forecast_time_24h
    expected_data_path = Path(fill_path(file_path=grib2_path, start_time=start_time, forecast_time=forecast_time))

    data_path = find_local_file(
        data_type=data_type,
        start_time=start_time,
        forecast_time=forecast_time,
    )

    assert data_path is not None
    assert data_path == expected_data_path
