import datetime
from typing import List, Union, Optional, Iterable
from pathlib import Path

import pandas as pd
from jinja2 import Template


def find_file(
        config: dict,
        data_level: Union[str, List],
        start_time: Union[datetime.datetime, pd.Timestamp],
        forecast_time: pd.Timedelta,
        obs_time: pd.Timedelta = None,
        **kwargs
) -> Optional[Path]:
    query_vars = QueryVars()

    for key in config["query"]:
        setattr(query_vars, key, config["query"][key])
    for key in kwargs:
        setattr(query_vars, key, kwargs[key])

    time_vars = TimeVars(start_time=start_time, forecast_time=forecast_time)
    if obs_time is not None:
        obs_time_vars = TimeVars(start_time=obs_time)
        setattr(query_vars, "obs_time", obs_time_vars)

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


def render_file_name(
        config: dict,
        start_time: Union[datetime.datetime, pd.Timestamp],
        forecast_time: Union[pd.Timedelta, str],
        obs_time: Optional[pd.Timedelta] = None,
        **kwargs
):
    query_vars = QueryVars()

    for key in config["query"]:
        setattr(query_vars, key, config["query"][key])
    for key in kwargs:
        setattr(query_vars, key, kwargs[key])

    time_vars = TimeVars(start_time=start_time, forecast_time=forecast_time)
    if obs_time is not None:
        obs_time_vars = TimeVars(start_time=obs_time)
        setattr(query_vars, "obs_time", obs_time_vars)

    parse_template = generate_template_parser(time_vars, query_vars)
    if "file_name" in config:
        file_name = parse_template(config["file_name"])
    elif "file_names" in config:
        file_name = parse_template(config["file_names"][0])
    return file_name


def find_files(
        config: dict,
        data_level: Union[str, List],
        start_time: Union[datetime.datetime, pd.Timestamp],
        forecast_time: pd.Timedelta,
        glob: bool = True,
        **kwargs
) -> Optional[List[Path]]:
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


def check_data_level(data_level, required_level: Optional[Union[str, Iterable]]):
    if required_level is None:
        return True
    elif isinstance(required_level, str):
        return data_level == required_level
    elif isinstance(required_level, Iterable):
        return data_level in required_level
    else:
        raise ValueError(f"level is not supported {required_level}")


def get_hour(forecast_time: pd.Timedelta) -> int:
    return int(forecast_time.seconds/3600) + forecast_time.days * 24


class QueryVars:
    def __init__(self):
        self.storage_base = None


class TimeVars:
    def __init__(
            self,
            start_time: Union[datetime.datetime, pd.Timestamp],
            forecast_time: Union[pd.Timedelta, str] = pd.Timedelta(hours=0)
    ):
        self.Year = start_time.strftime("%Y")
        self.Month = start_time.strftime("%m")
        self.Day = start_time.strftime("%d")
        self.Hour = start_time.strftime("%H")
        self.Minute = start_time.strftime("%M")

        if isinstance(forecast_time, pd.Timedelta):
            self.Forecast = f"{get_hour(forecast_time):03}"
        else:
            self.Forecast = forecast_time

        start_date_time_4dvar = start_time - datetime.timedelta(hours=3)
        self.Year4DV = start_date_time_4dvar.strftime("%Y")
        self.Month4DV = start_date_time_4dvar.strftime("%m")
        self.Day4DV = start_date_time_4dvar.strftime("%d")
        self.Minute4DV = start_time.strftime("%M")
        self.Hour4DV = start_date_time_4dvar.strftime("%H")


def generate_template_parser(time_vars, query_vars):

    def parse_template(template_content):
        template = Template(template_content)
        return template.render(time_vars=time_vars, query_vars=query_vars)

    return parse_template
