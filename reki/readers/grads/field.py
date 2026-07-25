from typing import Union, Optional, Literal
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


from .grads_ctl import GradsCtlParser
from .grads_data_handler import GradsDataHandler, GradsRecordHandler


def load_field_from_file(
        file_path: Union[str, Path],
        parameter: str,
        level_type: Optional[str] = None,
        level: Union[int, float, list] = None,
        level_dim: Optional[str] = None,
        latitude_direction: Literal["degree_north", "degree_south"] = "degree_north",
        valid_time: Union[str, pd.Timestamp] = None,
        forecast_time: Union[str, pd.Timedelta] = None,
        **kwargs
) -> Optional[xr.DataArray]:
    """
    Load one field or fields of one parameter from GrADS binary file.

    Parameters
    ----------
    file_path
        CTL description file path.
    parameter : str
        parameter name
    level_type : Optional[str]
        type of level

        * pl / ml
        * index
        * single
        * None
    level : Union[int, float, list]
        level value
    level_dim
    latitude_direction
        * degree_north
        * degree_south
    valid_time
    forecast_time
    kwargs

    Returns
    -------
    xr.DataArray
        Xarray DataArray if found, or None if not.

    Examples
    --------
    Get CMA-GFS GMF modelvar data file path.

    >>> from reki.data_finder import find_local_file
    >>> from reki.format.grads import load_field_from_file
    >>> modelvar_file_path = find_local_file(
    ...     "cma_gfs_gmf/bin/modelvar_ctl",
    ...     start_time="2024102600",
    ...     forecast_time="36h"
    ... )
    >>> modelvar_file_path
    PosixPath('/g3/COMMONDATA/OPER/CEMC/GFS_GMF/Fcst-long/2024102600/model.ctl_2024102600_036')

    Load a single level field:

    >>> field = load_field_from_file(
    ...     modelvar_file_path,
    ...     parameter="ts",
    ...     level_type="single",
    ... )
    >>> field
    <xarray.DataArray 'ts' (latitude: 1671, longitude: 2501)> Size: 17MB
    array([[276.65912, 276.66272, 276.66632, ..., 265.26233, 265.36075,
            265.45914],
           [271.72498, 271.74908, 272.00296, ..., 258.56754, 258.8194 ,
            265.57312],
           [271.73434, 271.7566 , 272.02072, ..., 259.0332 , 258.90613,
            265.68716],
           ...,
           [302.55112, 302.55115, 302.55112, ..., 302.75116, 302.75116,
            302.75116],
           [302.5451 , 302.5451 , 302.5451 , ..., 302.74515, 302.74515,
            302.74515],
           [302.53912, 302.53912, 302.53912, ..., 302.73914, 302.73914,
            302.73914]], dtype=float32)
    Coordinates:
      * latitude    (latitude) float64 13kB 60.1 60.07 60.04 ... 10.06 10.03 10.0
      * longitude   (longitude) float64 20kB 70.0 70.03 70.06 ... 144.9 145.0 145.0
        level       int64 8B 0
        valid_time  datetime64[ns] 8B ...
    Attributes:
        description:  surface temperature

    Load a multi level field:

    >>> field = load_field_from_file(
    ...     modelvar_file_path,
    ...     parameter="pi",
    ...     level_type="ml",
    ...     level=[1,2,3,4]
    ... )
    >>> field
    <xarray.DataArray 'pi' (ml: 4, latitude: 1441, longitude: 2880)> Size: 66MB
    array([[[0.9994781 , 0.99947816, 0.9994783 , ..., 0.99947804,
             0.9994781 , 0.99947816],
            [0.9994006 , 0.99940056, 0.9994005 , ..., 0.99940073,
             0.9994006 , 0.9994006 ],
            [0.99941564, 0.9994156 , 0.9994156 , ..., 0.99941593,
             0.9994159 , 0.99941576],
            ...,
            [0.9025082 , 0.90250385, 0.90249956, ..., 0.902521  ,
             0.9025168 , 0.9025125 ],
            [0.9023999 , 0.90239733, 0.9023947 , ..., 0.90240735,
             0.9024049 , 0.90240246],
            [0.90238315, 0.90238225, 0.90238154, ..., 0.9023854 ,
             0.9023846 , 0.9023839 ]],
           [[0.9987454 , 0.99874544, 0.99874544, ..., 0.9987453 ,
             0.9987453 , 0.9987454 ],
            [0.9986675 , 0.9986674 , 0.99866736, ..., 0.9986676 ,
             0.99866754, 0.9986675 ],
            [0.99867845, 0.9986784 , 0.9986783 , ..., 0.99867874,
             0.9986786 , 0.99867857],
    ...
            [0.90097326, 0.90096897, 0.9009646 , ..., 0.90098614,
             0.90098184, 0.90097755],
            [0.9008647 , 0.9008622 , 0.90085965, ..., 0.9008723 ,
             0.9008698 , 0.9008672 ],
            [0.9008468 , 0.900846  , 0.9008453 , ..., 0.90084904,
             0.90084827, 0.90084755]],
           [[0.99662673, 0.9966268 , 0.99662685, ..., 0.9966266 ,
             0.9966266 , 0.9966267 ],
            [0.996547  , 0.9965469 , 0.9965469 , ..., 0.9965471 ,
             0.99654704, 0.99654704],
            [0.9965461 , 0.99654603, 0.99654603, ..., 0.99654627,
             0.9965462 , 0.99654615],
            ...,
            [0.8998071 , 0.89980286, 0.8997985 , ..., 0.8998199 ,
             0.8998157 , 0.89981145],
            [0.89969814, 0.8996955 , 0.899693  , ..., 0.89970565,
             0.89970315, 0.89970064],
            [0.8996787 , 0.89967805, 0.8996773 , ..., 0.89968103,
             0.89968026, 0.8996795 ]]], dtype=float32)
    Coordinates:
      * latitude       (latitude) float64 12kB 90.0 89.88 89.75 ... -89.88 -90.0
      * longitude      (longitude) float64 23kB 0.0 0.125 0.25 ... 359.6 359.8 359.9
      * ml             (ml) float64 32B 1.0 2.0 3.0 4.0
        valid_time     datetime64[ns] 8B ...
        start_time     datetime64[ns] 8B ...
        forecast_time  timedelta64[ns] 8B 1 days 12:00:00
    Attributes:
        description:  PI

    Get CMA-MESO postvar data file path.

    >>> postvar_file_path = find_local_file(
    ...     "cma_meso_3km/bin/postvar_ctl",
    ...     start_time="2024102600",
    ... )
    >>> postvar_file_path
    PosixPath('/g3/COMMONDATA/OPER/CEMC/MESO_3KM/Fcst-main/2024102600/postvar.ctl_202410260000000')

    Load a field. Set ``forecast_time`` option because all data files of one cycle use one CTL file.

    >>> field = load_field_from_file(
    ...     postvar_file_path,
    ...     parameter="t",
    ...     level_type="pl",
    ...     forecast_time="24h",
    ... )
    >>> field
    <xarray.DataArray 't' (pl: 26, latitude: 1671, longitude: 2501)> Size: 435MB
    array([[[275.32828, 275.32657, 275.3065 , ..., 260.2067 , 260.09564,
             259.9529 ],
            [275.34738, 275.35904, 275.31445, ..., 260.0906 , 259.94995,
             259.89807],
            [275.40707, 275.39713, 275.38556, ..., 260.17816, 259.95865,
             259.75906],
            ...,
            [299.74286, 299.75177, 299.7522 , ..., 300.81787, 300.75705,
             300.7689 ],
            [299.73053, 299.7287 , 299.73077, ..., 300.78677, 300.80746,
             300.80475],
            [299.73132, 299.7241 , 299.72073, ..., 300.7902 , 300.8348 ,
             300.81497]],
           [[274.36758, 274.35873, 274.33942, ..., 258.95673, 258.8462 ,
             258.70416],
            [274.3802 , 274.38016, 274.39774, ..., 258.84058, 258.70056,
             258.64957],
            [274.4292 , 274.4326 , 274.42468, ..., 258.92773, 258.70926,
             258.51123],
    ...
            [221.9119 , 221.9043 , 221.90732, ..., 220.80681, 220.79927,
             220.79141],
            [221.9006 , 221.89711, 221.89825, ..., 220.78723, 220.77835,
             220.76967],
            [221.88934, 221.88995, 221.89085, ..., 220.76501, 220.7564 ,
             220.74776]],
           [[218.22253, 218.22556, 218.22949, ..., 225.40901, 225.4072 ,
             225.40222],
            [218.22551, 218.2267 , 218.22943, ..., 225.07826, 225.0852 ,
             225.40283],
            [218.2302 , 218.23157, 218.23302, ..., 225.08052, 225.0856 ,
             225.39835],
            ...,
            [234.57108, 234.70776, 234.7125 , ..., 232.78271, 232.81221,
             232.84262],
            [234.57117, 234.64745, 234.65125, ..., 232.78842, 232.81712,
             232.84677],
            [234.57133, 234.57503, 234.57837, ..., 232.82465, 232.83774,
             232.85094]]], dtype=float32)
    Coordinates:
      * latitude    (latitude) float64 13kB 60.1 60.07 60.04 ... 10.06 10.03 10.0
      * longitude   (longitude) float64 20kB 70.0 70.03 70.06 ... 144.9 145.0 145.0
      * pl          (pl) float64 208B 1e+03 975.0 950.0 925.0 ... 30.0 20.0 10.0
        valid_time  datetime64[ns] 8B ...
    Attributes:
        description:  temperature
    """
    if isinstance(forecast_time, str):
        forecast_time = pd.to_timedelta(forecast_time)
    if isinstance(file_path, str):
        file_path = Path(file_path)
    if isinstance(valid_time, str):
        valid_time = pd.to_datetime(valid_time)

    ctl_parser = GradsCtlParser()
    ctl_parser.parse(file_path)
    grads_ctl = ctl_parser.grads_ctl

    # level_type: pl, index, single
    grads_level_type = "multi"
    level_dim_name = "level"

    if not isinstance(level, list) and level is not None:
        level = [level]

    if level_type == "single":
        level = [0]
        grads_level_type = "single"
    elif level_type == "index":
        level = [grads_ctl.zdef["values"][cur_level] for cur_level in level]
    elif level_type in ("pl", "ml"):
        level_dim_name = level_type
        if level is None:
            level = grads_ctl.zdef["values"]
    elif level_type is None:
        grads_level_type = None
        # level = None

    if level_dim is not None:
        level_dim_name = level_dim

    data_handler = GradsDataHandler(grads_ctl)

    xarray_records = []
    for index, record in enumerate(grads_ctl.record):
        if not check_record(
            record,
            parameter=parameter,
            level=level,
            level_type=grads_level_type,
            valid_time=valid_time,
            forecast_time=forecast_time,
        ):
            continue

        offset = data_handler.get_offset_by_record_index(record["record_index"])
        record_handler = GradsRecordHandler(grads_ctl, index, offset)

        xarray_record = create_data_array_from_record(
            record=record_handler,
            parameter=parameter,
            level=record["level"],
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


def check_record(
        record: dict,
        parameter: str,
        level_type: str = None,
        level: Union[int, float, list] = None,
        valid_time: pd.Timestamp = None,
        forecast_time: pd.Timedelta = None
) -> bool:
    if parameter != record["name"]:
        return False

    if level_type is not None and level_type != record["level_type"]:
        return False

    if level is not None:
        if isinstance(level, list):
            if record["level"] not in level:
                return False
        else:
            if level != record["level"]:
                return False

    if valid_time is not None and valid_time != record["valid_time"]:
        return False

    if forecast_time is not None and forecast_time != record["forecast_time"]:
        return False

    return True


def create_data_array_from_record(
        record: GradsRecordHandler,
        parameter,
        level,
        level_dim_name=None,
        latitude_direction="degree_north",
) -> Optional[xr.DataArray]:
    grads_ctl = record.grads_ctl

    # values
    file_path = grads_ctl.get_data_file_path(record.record_info)
    with open(file_path, "rb") as f:
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
