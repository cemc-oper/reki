from typing import Union, Dict, List, Optional
from pathlib import Path

import numpy as np
import xarray as xr


from .grads_ctl import GradsCtlParser
from .grads_data_handler import GradsDataHandler, GradsRecordHandler


def load_field_from_file(
        file_path: Union[str, Path],
        parameter: Union[str, Dict] = None,
        level_type: str = None,
        level: Union[int, float, List] = None,
        level_dim: Optional[str] = None,
        latitude_direction: str = "degree_north",
        **kwargs
) -> Optional[xr.DataArray]:
    """
    Load one field or fields of one parameter from GrADS binary file.

    Parameters
    ----------
    file_path
    parameter
    level_type: str
        * pl / ml
        * index
        * single
        * None
    level
    level_dim
    latitude_direction:
        * degree_north
        * degree_south
    kwargs

    Returns
    -------
    xr.DataArray
        Xarray DataArray if found, or None if not.
    """
    ctl_parser = GradsCtlParser()
    ctl_parser.parse(file_path)
    grads_ctl = ctl_parser.grads_ctl

    # level_type: pl, index, single
    grads_level_type = "multi"
    level_dim_name = "level"
    if not isinstance(level, List):
        level = [level]
    if level_type == "single":
        level = np.zeros(len(level))
        grads_level_type = "single"
    elif level_type == "index":
        level = [grads_ctl.zdef["values"][cur_level] for cur_level in level]
    elif level_type in ("pl", "ml"):
        level_dim_name = level_type
    if level_dim is not None:
        level_dim_name = level_dim

    data_handler = GradsDataHandler(grads_ctl)

    xarray_records = []
    for cur_level in level:
        record = data_handler.find_record(
            name=parameter,
            level=cur_level,
            level_type=grads_level_type,
        )
        if record is None:
            continue

        xarray_record = create_data_array_from_record(
            record=record,
            parameter=parameter,
            level=cur_level,
            level_dim_name=level_dim_name,
            latitude_direction=latitude_direction,
        )
        xarray_records.append(xarray_record)

    record_count = len(xarray_records)
    if record_count == 0:
        return None
    elif record_count == 1:
        return xarray_records[0]
    else:
        data = xr.concat(xarray_records, level_dim_name)

    return data


def create_data_array_from_record(
        record: GradsRecordHandler,
        parameter,
        level,
        level_dim_name=None,
        latitude_direction="degree_north",
) -> Optional[xr.DataArray]:
    grads_ctl = record.grads_ctl

    # values
    with open(grads_ctl.dset, "rb") as f:
        values = record.load_data(f)

    # coords
    lons = grads_ctl.xdef["values"]
    lats = grads_ctl.ydef["values"]

    if latitude_direction == "degree_north":
        values = np.flip(values, 0)
        lats = lats[::-1]

    coords = {}
    coords["latitude"] = xr.Variable(
        "latitude",
        lats,
        attrs={
            "units": latitude_direction,
            "standard_name": "latitude",
            "long_name": "latitude"
        },
    )
    coords["longitude"] = xr.Variable(
        "longitude",
        lons,
        attrs={
            "units": "degrees_east",
            "standard_name": "longitude",
            "long_name": "longitude"
        }
    )

    coords[level_dim_name] = level
    coords["valid_time"] = record.record_info["valid_time"]

    if grads_ctl.start_time is not None and grads_ctl.forecast_time is not None:
        coords["start_time"] = grads_ctl.start_time
        coords["forecast_time"] = grads_ctl.forecast_time

    # dims
    dims = ("latitude", "longitude")

    # attrs
    data_attrs = {
        "description": record.record_info["description"]
    }

    data = xr.DataArray(
        values,
        dims=dims,
        coords=coords,
        attrs=data_attrs,
        name=parameter,
    )

    return data
