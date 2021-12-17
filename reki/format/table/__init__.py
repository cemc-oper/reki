from typing import Union, List, Dict
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


NWPC_OBS_CONFIG = {
    "RGWST": {
        "columns": [
            "Station_Id_C", "Station_Id_d", "Lat", "Lon", "Alti", "Day", "Hour",
            "PRS_Sea", "TEM", "DPT", "WIN_D_INST", "WIN_S_INST", "PRE_1h", "PRE_6h", "PRE_24h", "PRS",
            "Q_PRS_Sea", "Q_TEM", "Q_DPT", "Q_WIN_D_INST", "Q_WIN_S_INST", "Q_PRE_1h", "Q_PRE_6h", "Q_PRE_24h", "Q_PRS",
        ]
    },
    "RSURF": {
        "columns": [
            "Station_Id_C", "Station_Id_d", "Lat", "Lon", "Alti", "Day", "Hour", "Min",
            "PRS_HWC", "EVSS", "GPH", "TEM", "DPT", "WIN_D", "WIN_S", "Time_Dev_WQ", "Lat_Dev", "Lon_Dev",
            "Q_PRS_HWC", "Q_GPH", "Q_TEM", "Q_DPT", "Q_WIN_D", "Q_WIN_S"
        ]
    },
    "R2CWE": {
        "columns": [
            "SATE_ID", "Lat", "Lon", "Day", "HourMin", "V02023",
            "PRS_HWC", "V12071", "WIN_D", "WIN_S",
            "Q07004_001", "Q12071_001", "Q11001_001", "Q11002_001",
        ]
    },
    "RSING": {
        "columns": [
            "Station_Id_C", "Lat", "Lon", "Day", "HourMin", "Flight_Stat",
            "Flight_Heigh", "TEM", "WIN_D", "WIN_S",
            "Q_Flight_Heigh", "Q_TEM", "Q_WIN_D", "Q_WIN_S",
        ]
    },
    "RTEMP": {
        "header_columns": [
            "Station_Id_d", "Lat", "Lon", "Alti", "Day", "HourMin", "count"
        ],
        "columns": [
            "PRS_HWC", "EVSS", "GPH", "TEM", "DPT", "WIN_D", "WIN_S", "Time_Dev_WQ", "Lat_Dev", "Lon_Dev",
            "Q_PRS_HWC", "Q_GPH", "Q_TEM", "Q_DPT", "Q_WIN_D", "Q_WIN_S",
        ]
    }
}


def load_nwpc_obs_from_file(
    file_path: Union[Path, str],
) -> pd.DataFrame:
    """
    Load obs text file generated by GRAPES models.

    Supported obs file:

    * RGWST
    * RSURF
    * R2CWE
    * RSING
    * RTEMP

    Parameters
    ----------
    file_path
        obs file path.
    Returns
    -------
    pd.DataFrame
    """
    with open(file_path, "r") as f:
        lines = f.readlines()

    info_line = lines.pop(0)
    tokens = info_line.split()
    if len(tokens) not in (9, 10):
        raise ValueError("first line must have 9 or 10 tokens")
    obs_type = tokens[0]
    obs_time = pd.Timestamp(
        year=int(tokens[1]),
        month=int(tokens[2]),
        day=int(tokens[3]),
        hour=int(tokens[4])
    )

    config = NWPC_OBS_CONFIG.get(obs_type)

    if obs_type == "RTEMP":
        df = _load_nwpc_rtemp_data(lines, config)
    else:
        df = _load_nwpc_obs_table(lines, config)

    df["obs_time"] = obs_time
    return df


def _load_nwpc_obs_table(lines, config):
    sio = StringIO("")
    t = ""
    for index, line in enumerate(lines):
        if index % 2 == 0 and index > 0:
            t = t.strip()
            sio.write(t + "\n")
            t = ""
        t += "     " + line.strip()
    sio.seek(0)

    df = pd.read_table(
        sio,
        sep=r"\s+",
        names=config["columns"]
    )
    sio.close()
    return df


def _load_nwpc_rtemp_data(lines: List[str], config: Dict) -> pd.DataFrame:
    dfs = []
    while len(lines) > 0:
        line = lines.pop(0)
        sio = StringIO(line)
        station_header = pd.read_table(
            sio,
            sep=r"\s+",
            names=config["header_columns"]
        ).loc[0]
        sio.close()
        count = int(station_header["count"])

        sio = StringIO(line)
        for _ in range(count):
            sio.write(lines.pop(0))
        sio.seek(0)
        station_df = pd.read_table(
            sio,
            sep=r"\s+",
            names=config["columns"]
        )
        sio.close()

        # NEED improvement
        for i, v in list(station_header.items())[:-1]:
            station_df[i] = v

        columns_order = config["header_columns"][:-1] + config["columns"]
        station_df = station_df[columns_order]

        dfs.append(station_df)

    df = pd.concat(dfs, ignore_index=True)
    return df