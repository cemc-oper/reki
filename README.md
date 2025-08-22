# reki

![GitHub Release](https://img.shields.io/github/v/release/cemc-oper/reki)
![PyPI - Version](https://img.shields.io/pypi/v/reki)
[![Documentation Status](https://readthedocs.org/projects/reki/badge/?version=latest)](https://reki.readthedocs.io/zh_CN/latest/?badge=latest)
![GitHub License](https://img.shields.io/github/license/cemc-oper/cedarkit-maps)
![GitHub Action Workflow Status](https://github.com/cemc-oper/reki/actions/workflows/ci.yaml/badge.svg)

A data preparation tool for meteorological data in CEMC/CMA.

Load GRIB2 data using [eccodes](https://github.com/ecmwf/eccodes-python)
or [cfgrib](https://github.com/ecmwf/cfgrib).

中文文档 (Chinese documentation): https://reki.readthedocs.io/

## Installation

Install from pip:

```bash
pip install reki
```

or download the latest source code from GitHub and install using `pip`.

`reki` uses ecCodes to decode GRIB files
(which is needed by [eccodes](https://github.com/ecmwf/eccodes-python) and [cfgrib](https://github.com/ecmwf/cfgrib)). 
Please install ecCodes through conda or other package source.

## Getting started

### Local file lookup

The reki library includes built-in config files to locate data files in the CMA National Meteorological Supercomputing System 1 (CMA-HPC2023-SC1) shared file system (`/g3/COMMONDATA`).
The codes below finds the GRIB2-ORIG file path for CMA-GFS:

```pycon
>>> from reki.data_finder import find_local_file
>>> gfs_grib2_file_path = find_local_file(
...     "cma_gfs_gmf/grib2/orig",
...     start_time="2025081900",
...     forecast_time="24h",
... )
>>> gfs_grib2_file_path
PosixPath('/g3/COMMONDATA/OPER/CEMC/GFS_GMF/Prod-grib/2025081900/ORIG/gmf.gra.2025081900024.grb2')
```

The `find_local_file` function supports additional parameters for more specific file selection. 
For instance, using number to indicate ensemble member:

```pycon
>>> geps_grib2_file_path = find_local_file(
...     "cma_geps/grib2/orig",
...     start_time="2025081900",
...     forecast_time="24h",
...     number=2,
... )
>>> geps_grib2_file_path
PosixPath('/g3/COMMONDATA/OPER/CEMC/GEPS/Prod-grib/2025081900/grib2/gef.gra.002.2025081900024.grb2')
```

reki also supports locating intermediate model output files. 
The example below find path of the 240-hour model-level binary data file for CMA-GFS:

```pycon
>>> gfs_modelvar_file_path = find_local_file(
...     "cma_gfs_gmf/bin/modelvar",
...     start_time="2025081900",
...     forecast_time="240h",
... )
>>> gfs_modelvar_file_path
PosixPath('/g3/COMMONDATA/OPER/CEMC/GFS_GMF/Fcst-long/2025081900/modelvar2025081900_240')
```

Built-in configuration files are located in the `reki/data_finder/conf` directory.

### Reading GRIB2 files

#### Basic method

Use **eccodes** to retrieve a field from a GRIB2 file and return an `xarray.DataArray` object.
This example loads the 850 hPa temperature field from a CMA-GFS GRIB2-ORIG data:

```pycon
>>> from reki.format.grib.eccodes import load_field_from_file
>>> field = load_field_from_file(
...     gfs_grib2_file_path,
...     parameter="t",
...     level_type="pl",
...     level=850,
... )
>>> field
<xarray.DataArray 't' (latitude: 1440, longitude: 2880)> Size: 33MB
array([[270.49505859, 270.50505859, 270.50505859, ..., 270.49505859,
        270.49505859, 270.49505859],
       [270.69505859, 270.70505859, 270.71505859, ..., 270.70505859,
        270.70505859, 270.69505859],
       [270.84505859, 270.85505859, 270.85505859, ..., 270.84505859,
        270.84505859, 270.84505859],
       ...,
       [247.60505859, 247.58505859, 247.74505859, ..., 247.62505859,
        247.63505859, 247.61505859],
       [247.26505859, 247.26505859, 247.25505859, ..., 247.25505859,
        247.25505859, 247.25505859],
       [246.84505859, 246.84505859, 246.84505859, ..., 246.85505859,
        246.84505859, 246.84505859]], shape=(1440, 2880))
Coordinates:
    time        datetime64[ns] 8B 2025-08-19
    step        timedelta64[ns] 8B 1 days
    valid_time  datetime64[ns] 8B 2025-08-20
    pl          float64 8B 850.0
  * latitude    (latitude) float64 12kB 89.94 89.81 89.69 ... -89.81 -89.94
  * longitude   (longitude) float64 23kB 0.0 0.125 0.25 ... 359.6 359.8 359.9
Attributes: (12/17)
    GRIB_edition:             2
    GRIB_centre:              babj
    GRIB_subCentre:           0
    GRIB_tablesVersion:       4
    GRIB_localTablesVersion:  0
    GRIB_dataType:            fc
    ...                       ...
    GRIB_stepType:            instant
    GRIB_stepUnits:           1
    GRIB_stepRange:           24
    GRIB_endStep:int:         24
    GRIB_count:               109
    long_name:                discipline=0 parmcat=0 parm=0
```

Quick plotting:

```pycon
>>> (field - 273.15).plot()
```

#### Level Type

Load variables from model-level data. 
The example below loads the u-component at model level 10 (`ml`) from CMA-GFS model-level GRIB2 data:

```pycon
>>> gfs_model_grib2_file_path = find_local_file(
...     "cma_gfs_gmf/grib2/modelvar",
...     start_time="2025081900",
...     forecast_time="24h",
... )
>>> gfs_model_grib2_file_path
PosixPath('/g3/COMMONDATA/OPER/CEMC/GFS_GMF/Prod-grib/2025081900/MODELVAR/modelvar2025081900024.grb2')
>>> field = load_field_from_file(
...     gfs_model_grib2_file_path,
...     parameter="u",
...     level_type="ml",
...     level=10,
... )
>>> field
<xarray.DataArray 'u' (latitude: 1440, longitude: 2880)> Size: 33MB
array([[ 9.09106934,  9.09106934,  9.10106934, ...,  9.09106934,
         9.09106934,  9.09106934],
       [ 8.00106934,  8.00106934,  8.00106934, ...,  8.01106934,
         8.01106934,  8.01106934],
       [ 7.97106934,  7.96106934,  7.96106934, ...,  7.97106934,
         7.97106934,  7.97106934],
       ...,
       [11.00106934, 10.99106934, 10.98106934, ..., 11.04106934,
        11.03106934, 11.01106934],
       [11.73106934, 11.72106934, 11.71106934, ..., 11.77106934,
        11.75106934, 11.74106934],
       [14.21106934, 14.20106934, 14.19106934, ..., 14.24106934,
        14.23106934, 14.22106934]], shape=(1440, 2880))
Coordinates:
    time        datetime64[ns] 8B 2025-08-19
    step        timedelta64[ns] 8B 1 days
    valid_time  datetime64[ns] 8B 2025-08-20
    ml          int64 8B 10
  * latitude    (latitude) float64 12kB 89.94 89.81 89.69 ... -89.81 -89.94
  * longitude   (longitude) float64 23kB 0.0 0.125 0.25 ... 359.6 359.8 359.9
Attributes: (12/17)
    GRIB_edition:             2
    GRIB_centre:              babj
    GRIB_subCentre:           0
    GRIB_tablesVersion:       4
    GRIB_localTablesVersion:  0
    GRIB_dataType:            fc
    ...                       ...
    GRIB_stepType:            instant
    GRIB_stepUnits:           1
    GRIB_stepRange:           24
    GRIB_endStep:int:         24
    GRIB_count:               187
    long_name:                discipline=0 parmcat=2 parm=2
```

#### More filtering options

The `load_field_from_file` function also supports passing GRIB key parameters directly via a dictionary.
The example below loads the radar reflectivity field at 850 hPa:

```pycon
>>> field = load_field_from_file(
...     gfs_grib2_file_path,
...     parameter={
...         "discipline": 0,
...         "parameterCategory": 16,
...         "parameterNumber": 225,
...     },
...     level_type="pl",
...     level=850,
... )
>>> field
<xarray.DataArray '0_16_225' (latitude: 1440, longitude: 2880)> Size: 33MB
array([[-7.12, -7.17, -7.24, ..., -7.03, -7.04, -7.06],
       [-7.71, -7.64, -7.65, ..., -7.82, -7.8 , -7.78],
       [-6.03, -6.07, -6.08, ..., -6.07, -6.08, -6.08],
       ...,
       [ 1.52,  1.37,  1.18, ...,  1.59,  1.22,  1.23],
       [ 0.65,  0.68,  1.31, ...,  0.65,  0.67,  0.69],
       [-0.22, -0.2 , -0.21, ..., -0.25, -0.24, -0.24]],
      shape=(1440, 2880))
Coordinates:
    time        datetime64[ns] 8B 2025-08-19
    step        timedelta64[ns] 8B 1 days
    valid_time  datetime64[ns] 8B 2025-08-20
    pl          float64 8B 850.0
  * latitude    (latitude) float64 12kB 89.94 89.81 89.69 ... -89.81 -89.94
  * longitude   (longitude) float64 23kB 0.0 0.125 0.25 ... 359.6 359.8 359.9
Attributes: (12/17)
    GRIB_edition:             2
    GRIB_centre:              babj
    GRIB_subCentre:           0
    GRIB_tablesVersion:       4
    GRIB_localTablesVersion:  1
    GRIB_dataType:            fc
    ...                       ...
    GRIB_stepType:            instant
    GRIB_stepUnits:           1
    GRIB_stepRange:           24
    GRIB_endStep:int:         24
    GRIB_count:               790
    long_name:                discipline=0 parmcat=16 parm=225
```

#### ecCodes interface

reki supports returning the raw GRIB message via the ecCodes Python API.
For instance, loading the 850 hPa geopotential height field:

```pycon
>>> from reki.format.grib.eccodes import load_message_from_file
>>> message = load_message_from_file(
...     gfs_grib2_file_path,
...     parameter="gh",
...     level_type="pl",
...     level=850,
... )
>>> message
94257262686816
>>> import eccodes
>>> values = eccodes.codes_get_double_array(message, "values")
>>> ni = eccodes.codes_get_long(message, "Ni")
>>> nj = eccodes.codes_get_long(message, "Nj")
>>> values.reshape(nj, ni)
array([[1425.48203125, 1425.48203125, 1425.48203125, ..., 1425.48203125,
        1425.48203125, 1425.48203125],
       [1428.68203125, 1428.68203125, 1428.68203125, ..., 1428.68203125,
        1428.68203125, 1428.68203125],
       [1431.18203125, 1431.18203125, 1431.18203125, ..., 1431.18203125,
        1431.18203125, 1431.18203125],
       ...,
       [1311.18203125, 1311.28203125, 1310.38203125, ..., 1311.08203125,
        1311.08203125, 1311.08203125],
       [1311.88203125, 1311.78203125, 1311.88203125, ..., 1311.88203125,
        1311.88203125, 1311.88203125],
       [1313.38203125, 1313.38203125, 1313.38203125, ..., 1313.28203125,
        1313.38203125, 1313.38203125]], shape=(1440, 2880))
```

Finally, release the GRIB message object:

```pycon
>>> eccodes.codes_release(message)
```

## Examples

See [cemc-oper/data-notebook](https://github.com/cemc-oper/data-notebook) project for more examples.

## LICENSE

Copyright &copy; 2020-2025, developers at cemc-oper.

`reki` is licensed under [Apache License, Version 2.0](./LICENSE)