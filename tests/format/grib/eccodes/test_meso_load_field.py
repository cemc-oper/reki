import pytest
import pandas as pd

from reki.data_finder import find_local_file
from reki.format.grib.eccodes import load_field_from_file


@pytest.fixture
def system_name():
    return "grapes_meso_3km"


@pytest.fixture
def file_path(system_name, start_time, forecast_time, storage_base):
    f = find_local_file(
        f"{system_name}/grib2/orig",
        start_time=start_time,
        forecast_time=forecast_time,
        storage_base=storage_base
    )
    return f


def test_load_with_short_name(file_path):
    short_name = "t"
    field = load_field_from_file(
        file_path,
        parameter=short_name,
        level_type="pl",
        level=850
    )
    assert field is not None


def test_load_with_extended_name(file_path):
    parameter = "TCOLW"
    field = load_field_from_file(
        file_path,
        parameter=parameter,
    )
    assert field is not None


def test_load_with_numbers(file_path):
    parameter = {
        "discipline": 0,
        "parameterCategory": 1,
        "parameterNumber": 225
    }
    level_type = "pl"
    level = 850
    field = load_field_from_file(
        file_path,
        parameter=parameter,
        level_type=level_type,
        level=level
    )
    assert field is not None
