from typing import Union
from pathlib import Path
from io import StringIO

import pandas as pd


def load_table_from_file(
        file_path: Union[str, Path],
        sep=r"\s+|,",
        **kwargs
) -> pd.DataFrame:
    """
    Load data from table file using ``pd.read_table``.

    Parameters
    ----------
    file_path
    sep
        ``sep`` option in ``pd.read_table()``
    **kwargs
        additional arguments for ``pd.read_table()``

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


def load_rgwst_from_file(
    file_path,
):
    with open(file_path, "r") as f:
        lines = f.readlines()

    info_line = lines[0]
    tokens = info_line.split()


    sio = StringIO("")
    t = ""
    for index, line in enumerate(lines[1:]):
        if index % 2 == 0 and index > 0:
            t = t.strip()
            sio.write(t + "\n")
            t = ""
        t += "     " + line.strip()
    sio.seek(0)
    df = pd.read_table(
        sio,
        sep=r"\s+",
        names=[
            "Station_Id_C", "Station_Id_d", "Lat", "Lon", "Alti", "Day", "Hour",
            "PRS_Sea", "TEM", "DPT", "WIN_D_INST", "WIN_S_INST", "PRE_1h", "PRE_6h", "PRE_24h", "PRS",
            "Q_PRS_Sea", "Q_TEM", "Q_DPT", "Q_WIN_D_INST", "Q_WIN_S_INST", "Q_PRE_1h", "Q_PRE_6h", "Q_PRE_24h", "Q_PRS",
        ]
    )
    sio.close()
    return df
