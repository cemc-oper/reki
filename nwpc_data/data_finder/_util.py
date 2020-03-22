import datetime
import typing
from pathlib import Path

import pandas as pd
from jinja2 import Template


def get_hour(forecast_time: pd.Timedelta) -> int:
    return int(forecast_time.seconds/3600) + forecast_time.days * 24


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


def generate_template_parser(start_time, forecast_time):
    time_vars = TimeVars(start_time=start_time, forecast_time=forecast_time)

    def parse_template(template_content):
        template = Template(template_content)
        return template.render(time_vars=time_vars)

    return parse_template


def check_level(path_level, level: str or typing.List):
    if isinstance(level, str):
        return path_level == level
    elif isinstance(level, typing.List):
        return path_level in level
    else:
        raise ValueError(f"level is not supported {level}")


def find_file(config: dict, start_time, forecast_time, level: str or typing.List) -> Path or None:
    parse_template = generate_template_parser(start_time, forecast_time)
    file_name = parse_template(config["file_name"])
    file_path = None
    paths = config["paths"]
    for a_path_object in paths:
        path_level = a_path_object["level"]
        if not check_level(path_level, level):
            continue

        path_template = a_path_object["path"]
        current_dir_path = parse_template(path_template)
        current_file_path = Path(current_dir_path, file_name)
        if current_file_path.is_file():
            file_path = current_file_path
            break

    return file_path
