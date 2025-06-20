import pytest
from dataclasses import dataclass, asdict

from reki.data_finder import find_local_file
from reki.format.grib.eccodes import load_field_from_file


@dataclass
class QueryOption:
    parameter: str
    level_type: str
    level: float


@dataclass
class TestCase:
    query: QueryOption


@pytest.fixture
def system_name():
    return "cma_meso_3km"


@pytest.fixture
def file_path(system_name, start_time, forecast_time, storage_base):
    f = find_local_file(
        f"{system_name}/grib2/orig",
        start_time=start_time,
        forecast_time=forecast_time,
        storage_base=storage_base
    )
    return f


@pytest.fixture
def modelvar_file_path(system_name, start_time, forecast_time, storage_base):
    f = find_local_file(
        f"{system_name}/grib2/modelvar",
        start_time=start_time,
        forecast_time=forecast_time,
        storage_base=storage_base
    )
    return f


def test_load_with_short_name(file_path):
    """
    Use short name supported by ecCodes
    """
    short_name = "t"
    field = load_field_from_file(
        file_path,
        parameter=short_name,
        level_type="pl",
        level=850
    )
    assert field is not None


def test_load_with_extended_name(file_path):
    """
    Use short name embedded by reki from wgrib2 and CEMC
    """
    parameter = "TCOLW"
    field = load_field_from_file(
        file_path,
        parameter=parameter,
    )
    assert field is not None


def test_load_with_numbers(file_path):
    """
    Use GRIB keys for parameter:

    * discipline
    * parameterCategory
    * parameterNumber
    """
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


def test_load_wind_10m(file_path):
    """
    Use ``stepType`` for normal and statistics fields.
    """
    parameter = "10u"

    # 10m U 风
    step_type = "instant"
    field_instant = load_field_from_file(
        file_path,
        parameter=parameter,
        stepType=step_type
    )
    assert field_instant is not None

    # 输出间隔内最大 10m U 风
    step_type = "max"
    field_max = load_field_from_file(
        file_path,
        parameter=parameter,
        stepType=step_type
    )
    assert field_max is not None


def test_load_ri(file_path):
    """
    Use different ``level_type`` for same parameter.

    地表理查森数
    边界层理查森数
    """
    parameter = "RI"
    level_type = "surface"
    field_surface = load_field_from_file(
        file_path,
        parameter=parameter,
        level_type=level_type
    )
    assert field_surface is not None

    level_type = {
        "typeOfFirstFixedSurface": 166
    }
    field_166 = load_field_from_file(
        file_path,
        parameter=parameter,
        level_type=level_type
    )
    assert field_166 is not None


def test_load_with_two_levels(file_path):
    """
    Use ``first_level`` and ``second_level`` in ``level`` option.

    土壤温度

    * 0-10cm below ground
    * 10-30cm below ground
    """
    parameter = "t"
    level_type = "depthBelowLandLayer"
    first_level = 0
    second_level = 0.1

    field_0_10 = load_field_from_file(
        file_path,
        parameter=parameter,
        level_type=level_type,
        level={
            "first_level": first_level,
            "second_level": second_level
        }
    )
    assert field_0_10 is not None

    first_level = 0.1
    second_level = 0.3

    field_10_30 = load_field_from_file(
        file_path,
        parameter=parameter,
        level_type=level_type,
        level={
            "first_level": first_level,
            "second_level": second_level
        }
    )
    assert field_10_30 is not None


def test_load_modelvar_using_level_type(modelvar_file_path):
    parameter = "t"
    level = 10
    level_type = "ml"
    field = load_field_from_file(
        modelvar_file_path,
        parameter=parameter,
        level_type=level_type,
        level=level
    )
    assert field is not None


def test_load_modelvar_using_cemc_param_table(modelvar_file_path):
    test_cases = [
        TestCase(QueryOption(parameter="pip", level_type="ml", level=30)),
    ]

    for test_case in test_cases:
        field = load_field_from_file(
            modelvar_file_path,
            **asdict(test_case.query)
        )
        assert field is not None
