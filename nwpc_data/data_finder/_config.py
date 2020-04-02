from pathlib import Path

import yaml


def find_config(config_dir, data_type: str, data_class: str = "od"):
    config_file_path = Path(config_dir, data_class, data_type+".yaml")
    if config_file_path.is_file():
        return config_file_path
    else:
        return None


def load_config(config_file_path):
    with open(config_file_path) as config_file:
        config = yaml.safe_load(config_file)
        return config


def get_default_local_config_path():
    return Path(Path(__file__).parent, "conf").absolute()
