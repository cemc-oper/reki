from pathlib import Path
from typing import Union, Optional


def find_config(
        config_dir: Union[str, Path],
        data_type: str,
        data_class: str = "od"
) -> Optional[Path]:
    """
    Find config YAML for some data type by combine ``config_dir``, ``data_type`` and ".yaml".

    Parameters
    ----------
    config_dir
    data_type
    data_class

    Returns
    -------
    Optional[Path]
        config file path, or None if not found.

    Examples
    --------
    Load config file for operation CMA-MESO 3KM grib2 orig product.

    .. code-block:: pycon

        >>> find_config("/path/to/config_dir", "cma_meso_3km/grib2/orig", "od")
        /path/to/config_dir/od/cma_meso_3km/grib2/orig.yaml

    If config YAML file is not found, return None.

    .. code-block:: pycon

        >>> find_config("/path/to/config_dir", "no_system/grib2/orig", "od")
        None

    """
    config_file_path = Path(config_dir, data_class, data_type + ".yaml")
    if config_file_path.is_file():
        return config_file_path
    else:
        return None


def load_config(config_file_path: Union[str, Path]) -> str:
    """
    load config dict from config file.

    Parameters
    ----------
    config_file_path

    Returns
    -------
    str
        config content
    """
    with open(config_file_path) as config_file:
        config_content = config_file.read()

    return config_content


def get_default_local_config_path() -> Path:
    """
    return default local config path in this package.
    """
    return Path(Path(__file__).parent, "conf").absolute()
