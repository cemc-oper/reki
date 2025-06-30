import datetime
from typing import Dict, List, Union, Optional, Iterable, Callable
from pathlib import Path

import yaml
import pandas as pd
from jinja2 import Template


def find_file(
        config_content: str,
        data_level: Union[str, List],
        start_time: Union[datetime.datetime, pd.Timestamp],
        forecast_time: pd.Timedelta,
        obs_time: Optional[pd.Timedelta] = None,
        debug: bool = False,
        **kwargs
) -> Optional[Path]:
    """
    Find a file according to config.

    Parameters
    ----------
    config_content
        config content string. An example of config file:

        .. code-block:: yaml

            file_name: 'modelvar{{ time_vars.Year }}{{ time_vars.Month }}{{ time_vars.Day }}{{ time_vars.Hour }}{{ time_vars.Forecast }}.grb2'

            paths:
              - type: local
                level: runtime
                path: "/some/path/to/{{ time_vars.Year }}{{ time_vars.Month }}{{ time_vars.Day }}{{ time_vars.Hour }}/data/output/grib2_orig/"

              - type: local
                level: storage
                path: '{{ query_vars.storage_base }}/GRAPES_GFS_GMF/Prod-grib/{{ time_vars.Year }}{{ time_vars.Month }}{{ time_vars.Day }}{{ time_vars.Hour }}/MODELVAR'

    data_level
    start_time
    forecast_time
    obs_time
    debug
        show debug info
    kwargs

    Returns
    -------
    Path if found, None otherwise
    """
    query_vars = QueryVars()

    # for key in config["query"]:
    #     setattr(query_vars, key, config["query"][key])
    for key in kwargs:
        setattr(query_vars, key, kwargs[key])

    time_vars = TimeVars(start_time=start_time, forecast_time=forecast_time)
    if obs_time is not None:
        obs_time_vars = TimeVars(start_time=obs_time)
        setattr(query_vars, "obs_time", obs_time_vars)

    parse_template = generate_template_parser(time_vars, query_vars)

    parsed_config_content = parse_template(config_content)
    config = yaml.safe_load(parsed_config_content)

    file_name = config["file_name"]
    if debug:
        print("file name:", file_name)
    file_path = None
    paths = config["paths"]
    for a_path_object in paths:
        current_data_level = a_path_object["level"]
        if not check_data_level(current_data_level, data_level):
            continue

        path_template = a_path_object["path"]
        current_dir_path = parse_template(path_template)
        current_file_path = Path(current_dir_path, file_name)
        if debug:
            print("searching file path:", current_file_path)
        if current_file_path.is_file():
            file_path = current_file_path
            break

    return file_path


def render_file_name(
        config_content: str,
        start_time: Union[datetime.datetime, pd.Timestamp],
        forecast_time: Union[pd.Timedelta, str],
        obs_time: Optional[pd.Timedelta] = None,
        **kwargs
):
    query_vars = QueryVars()

    # for key in config["query"]:
    #     setattr(query_vars, key, config["query"][key])
    # for key in kwargs:
    #     setattr(query_vars, key, kwargs[key])

    time_vars = TimeVars(start_time=start_time, forecast_time=forecast_time)
    if obs_time is not None:
        obs_time_vars = TimeVars(start_time=obs_time)
        setattr(query_vars, "obs_time", obs_time_vars)

    parse_template = generate_template_parser(time_vars, query_vars)
    parsed_config_content = parse_template(config_content)
    config = yaml.safe_load(parsed_config_content)

    if "file_name" in config:
        file_name = config["file_name"]
    elif "file_names" in config:
        file_name = config["file_names"][0]
    return file_name


def find_files(
        config_content: str,
        data_level: Union[str, List],
        start_time: Union[datetime.datetime, pd.Timestamp],
        forecast_time: pd.Timedelta,
        glob: bool = True,
        **kwargs
) -> Optional[List[Path]]:
    query_vars = QueryVars()

    # for key in config["query"]:
    #     setattr(query_vars, key, config["query"][key])
    # for key in kwargs:
    #     setattr(query_vars, key, kwargs[key])

    time_vars = TimeVars(start_time=start_time, forecast_time=forecast_time)

    parse_template = generate_template_parser(time_vars, query_vars)
    parsed_config_content = parse_template(config_content)
    config = yaml.safe_load(parsed_config_content)

    file_name = parse_template(config["file_name"])
    file_paths = []
    paths = config["paths"]
    for a_path_object in paths:
        current_data_level = a_path_object["level"]
        if not check_data_level(current_data_level, data_level):
            continue

        path_template = a_path_object["path"]
        current_dir_path = Path(path_template)
        current_files = current_dir_path.glob(file_name)
        file_paths.extend([f for f in current_files if f.is_file()])

    if len(file_paths) == 0:
        return None
    return file_paths


def check_data_level(data_level, required_level: Optional[Union[str, Iterable]]) -> bool:
    """
    check whether data level is in required level(s).

    Parameters
    ----------
    data_level
    required_level

    Returns
    -------
    bool
    """
    if required_level is None:
        return True
    elif isinstance(required_level, str):
        return data_level == required_level
    elif isinstance(required_level, Iterable):
        return data_level in required_level
    else:
        raise ValueError(f"level is not supported {required_level}")


class QueryVars:
    def __init__(self):
        self.storage_base = None


class TimeVars:
    def __init__(
            self,
            start_time: Union[datetime.datetime, pd.Timestamp],
            forecast_time: pd.Timedelta = pd.Timedelta(hours=0)
    ):
        self.start_time = start_time
        self.forecast_time = forecast_time

        self.year = start_time.strftime("%Y")
        self.month = start_time.strftime("%m")
        self.day = start_time.strftime("%d")
        self.hour = start_time.strftime("%H")
        self.minute = start_time.strftime("%M")

        self.forecast_hour = f"{get_forecast_hour(forecast_time):03}"
        self.forecast_minute = f"{get_forecast_minute(forecast_time):02}"


def generate_template_parser(time_vars: Dict, query_vars: Dict) -> Callable:

    def parse_template(template_content):
        template = Template(template_content)
        return template.render(
            time_vars=time_vars,
            query_vars=query_vars,
            get_year=get_year,
            get_month=get_month,
            get_day=get_day,
            get_hour=get_hour,
            get_minute=get_minute,
            get_forecast_hour=get_forecast_hour,
            get_forecast_minute=get_forecast_minute,
            generate_start_time=generate_start_time,
            generate_forecast_time=generate_forecast_time,
        )

    return parse_template


def get_year(start_time: pd.Timestamp) -> str:
    return f"{start_time.year:04d}"


def get_month(start_time: pd.Timestamp) -> str:
    return f"{start_time.month:02d}"


def get_day(start_time: pd.Timestamp) -> str:
    return f"{start_time.day:02d}"


def get_hour(start_time: pd.Timestamp) -> str:
    return f"{start_time.hour:02d}"


def get_minute(start_time: pd.Timestamp) -> str:
    return f"{start_time.minute:02d}"


def get_forecast_hour(forecast_time: pd.Timedelta) -> int:
    return int(forecast_time.seconds/3600) + forecast_time.days * 24


def get_forecast_minute(forecast_time: pd.Timedelta) -> int:
    return forecast_time.components.minutes


def generate_start_time(star_time: pd.Timestamp, hour: int):
    return star_time + pd.Timedelta(hours=hour)


def generate_forecast_time(forecast_time: pd.Timedelta, time_interval: str):
    t = pd.to_timedelta(time_interval)
    return forecast_time + t
