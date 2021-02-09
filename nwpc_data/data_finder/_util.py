import datetime
import typing
from pathlib import Path

import pandas as pd
from jinja2 import Template


def find_file(
        config: dict,
        data_level: str or typing.List,
        start_time: datetime.datetime or pd.Timestamp,
        forecast_time: pd.Timedelta,
        **kwargs
) -> Path or None:
    query_vars = QueryVars()

    for key in config["query"]:
        setattr(query_vars, key, config["query"][key])
    for key in kwargs:
        setattr(query_vars, key, kwargs[key])

    time_vars = TimeVars(start_time=start_time, forecast_time=forecast_time)

    parse_template = generate_template_parser(time_vars, query_vars)
    file_name = parse_template(config["file_name"])
    file_path = None
    paths = config["paths"]
    for a_path_object in paths:
        current_data_level = a_path_object["level"]
        if not check_data_level(current_data_level, data_level):
            continue

        path_template = a_path_object["path"]
        current_dir_path = parse_template(path_template)
        current_file_path = Path(current_dir_path, file_name)
        if current_file_path.is_file():
            file_path = current_file_path
            break

    return file_path


def find_files(
        config: dict,
        data_level: str or typing.List,
        start_time: datetime.datetime or pd.Timestamp,
        forecast_time: pd.Timedelta,
        glob: bool = True,
        **kwargs
) -> typing.List[Path] or None:
    query_vars = QueryVars()

    for key in config["query"]:
        setattr(query_vars, key, config["query"][key])
    for key in kwargs:
        setattr(query_vars, key, kwargs[key])

    time_vars = TimeVars(start_time=start_time, forecast_time=forecast_time)

    parse_template = generate_template_parser(time_vars, query_vars)
    file_name = parse_template(config["file_name"])
    file_paths = []
    paths = config["paths"]
    for a_path_object in paths:
        current_data_level = a_path_object["level"]
        if not check_data_level(current_data_level, data_level):
            continue

        path_template = a_path_object["path"]
        current_dir_path = Path(parse_template(path_template))
        current_files = current_dir_path.glob(file_name)
        file_paths.extend([f for f in current_files if f.is_file()])

    if len(file_paths) == 0:
        return None
    return file_paths


def check_data_level(data_level, required_level: str or typing.Iterable or None):
    if required_level is None:
        return True
    elif isinstance(required_level, str):
        return data_level == required_level
    elif isinstance(required_level, typing.Iterable):
        return data_level in required_level
    else:
        raise ValueError(f"level is not supported {required_level}")


def get_hour(forecast_time: pd.Timedelta) -> int:
    return int(forecast_time.seconds/3600) + forecast_time.days * 24


class QueryVars(object):
    pass


class TimeVars(object):
    def __init__(self, start_time: datetime.datetime or pd.Timestamp, forecast_time: pd.Timedelta):
        self.Year = start_time.strftime("%Y")
        self.Month = start_time.strftime("%m")
        self.Day = start_time.strftime("%d")
        self.Hour = start_time.strftime("%H")
        self.Forecast = f"{get_hour(forecast_time):03}"

        start_date_time_4dvar = start_time - datetime.timedelta(hours=3)
        self.Year4DV = start_date_time_4dvar.strftime("%Y")
        self.Month4DV = start_date_time_4dvar.strftime("%m")
        self.Day4DV = start_date_time_4dvar.strftime("%d")
        self.Hour4DV = start_date_time_4dvar.strftime("%H")


def generate_template_parser(time_vars, query_vars):

    def parse_template(template_content):
        template = Template(template_content)
        return template.render(time_vars=time_vars, query_vars=query_vars)

    return parse_template
