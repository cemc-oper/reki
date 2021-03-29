import typing
from pathlib import Path

import pandas as pd


def load_table_from_file(
        file_path: typing.Union[str, Path],
        sep="\s+|,",
        **kwargs
) -> pd.DataFrame:
    """
    Load data from table file using `pd.read_table`.

    Parameters
    ----------
    file_path: str or Path
    sep: str
    kwargs:
        additional arguments for `pd.read_table()`

    Returns
    -------
    pd.DataFrame
    """
    df = pd.read_table(
        file_path,
        sep=sep,
        **kwargs
    )
    return df
