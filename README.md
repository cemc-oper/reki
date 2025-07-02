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

`reki` has several functions to help users to find one filed from a local GRIB 2 file.

`load_message_from_file` from `reki.format.grib.eccodes` returns a GRIB handler.
Users can use it to get attrs or values with functions from [eccodes](https://github.com/ecmwf/eccodes-python) .

For example, load 850hPa temperature from CMA-GFS and get values from the returned message.

```pycon
>>> from reki.format.grib.eccodes import load_message_from_file
>>> t = load_message_from_file(
...     file_path="/g3/COMMONDATA/OPER/CEMC/GFS_GMF/Prod-grib/2024040800/ORIG/gmf.gra.2024040800024.grb2",
...     parameter="t",
...     level_type="isobaricInhPa",
...     level=850,
... )
>>> data = eccodes.codes_get_double_array(t, "values")
>>> data = data.reshape([1440, 2880])
>>> data
array([[252.51597656, 252.51597656, 252.51597656, ..., 252.51597656,
        252.51597656, 252.50597656],
       [252.45597656, 252.45597656, 252.45597656, ..., 252.45597656,
        252.45597656, 252.45597656],
       [252.35597656, 252.35597656, 252.36597656, ..., 252.35597656,
        252.35597656, 252.35597656],
       ...,
       [234.68597656, 234.77597656, 234.77597656, ..., 234.19597656,
        234.28597656, 234.45597656],
       [234.20597656, 234.28597656, 234.61597656, ..., 234.55597656,
        234.40597656, 234.28597656],
       [234.24597656, 234.26597656, 234.28597656, ..., 234.26597656,
        234.25597656, 234.24597656]])
```

**NOTE**: Please release the handler using `eccodes.codes_release` manually.

`eccodes` engine also provides some functions to load array from GRIB2 file
in which GRIB2 message is loaded by [eccodes-python](https://github.com/ecmwf/eccodes-python)
and converted into `xarray.DataArray` by `reki`.

```pycon
>>> from reki.format.grib.eccodes import load_field_from_file
>>> load_field_from_file(
...     file_path="/g3/COMMONDATA/OPER/CEMC/GFS_GMF/Prod-grib/2024040800/ORIG/gmf.gra.2024040800024.grb2",
...     parameter="t",
...     level_type="pl",
...     level=850,
... )
<xarray.DataArray 't' (latitude: 1440, longitude: 2880)> Size: 33MB
array([[252.51597656, 252.51597656, 252.51597656, ..., 252.51597656,
        252.51597656, 252.50597656],
       [252.45597656, 252.45597656, 252.45597656, ..., 252.45597656,
        252.45597656, 252.45597656],
       [252.35597656, 252.35597656, 252.36597656, ..., 252.35597656,
        252.35597656, 252.35597656],
       ...,
       [234.68597656, 234.77597656, 234.77597656, ..., 234.19597656,
        234.28597656, 234.45597656],
       [234.20597656, 234.28597656, 234.61597656, ..., 234.55597656,
        234.40597656, 234.28597656],
       [234.24597656, 234.26597656, 234.28597656, ..., 234.26597656,
        234.25597656, 234.24597656]])
Coordinates:
    time        datetime64[ns] 8B 2024-04-08
    step        timedelta64[ns] 8B 1 days
    valid_time  datetime64[ns] 8B 2024-04-09
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
    GRIB_endStep:             24
    GRIB_count:               109
    long_name:                discipline=0 parmcat=0 parm=0
```

If the field doesn't have a `shortName`, use dict for `parameter`.

Load a filed without shortName.

```pycon
>>> load_field_from_file(
...     file_path="/g3/COMMONDATA/OPER/CEMC/GFS_GMF/Prod-grib/2024040800/ORIG/gmf.gra.2024040800024.grb2",
...     parameter={
...         "discipline": 0,
...         "parameterCategory": 2,
...         "parameterNumber": 225,
...     },
...     level_type="isobaricInhPa",
...     level=850,
... )
<xarray.DataArray '0_2_225' (latitude: 1440, longitude: 2880)> Size: 33MB
array([[ 1.96391602e-11,  1.96391602e-11, -1.03608398e-11, ...,
        -4.43608398e-11, -6.73608398e-11, -6.73608398e-11],
       [ 1.36391602e-11,  1.36391602e-11, -8.36083984e-12, ...,
        -3.03608398e-11, -3.83608398e-11, -3.83608398e-11],
       [ 1.66391602e-11,  1.66391602e-11,  1.46391602e-11, ...,
         9.63916016e-12,  1.56391602e-11,  1.56391602e-11],
       ...,
       [ 3.06391602e-11,  3.06391602e-11,  4.06391602e-11, ...,
        -4.36083984e-12, -3.53608398e-11, -3.53608398e-11],
       [ 6.56391602e-11,  6.56391602e-11,  6.26391602e-11, ...,
        -2.23608398e-11,  2.63916016e-12,  2.63916016e-12],
       [ 6.56391602e-11,  6.56391602e-11,  6.16391602e-11, ...,
        -2.23608398e-11,  2.63916016e-12,  2.63916016e-12]])
Coordinates:
    time           datetime64[ns] 8B 2024-04-08
    step           timedelta64[ns] 8B 1 days
    valid_time     datetime64[ns] 8B 2024-04-09
    isobaricInhPa  int64 8B 850
  * latitude       (latitude) float64 12kB 89.94 89.81 89.69 ... -89.81 -89.94
  * longitude      (longitude) float64 23kB 0.0 0.125 0.25 ... 359.6 359.8 359.9
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
    GRIB_endStep:             24
    GRIB_count:               826
    long_name:                discipline=0 parmcat=2 parm=225
```

## Engines

`reki` loads GRIB2 file using `eccodes` by default and also supports `cfgrib`.

### cfgrib

If you don't care about loading speed, please use [cfgrib](https://github.com/ecmwf/cfgrib) engine
with option `engine="cfgrib"`.

Please install cfgrib before using this engine.

Read 850hPa temperature from a CMA-GFS grib2 file using `shortName` key `t`.
( `shortName` is an ecCodes key. )

```pycon
>>> from reki.format.grib import load_field_from_file
>>> load_field_from_file(
...     file_path="/g3/COMMONDATA/OPER/CEMC/GFS_GMF/Prod-grib/2024040800/ORIG/gmf.gra.2024040800024.grb2",
...     parameter="t",
...     level_type="isobaricInhPa",
...     level=850,
...     engine="cfgrib",
... )
<xarray.DataArray 't' (latitude: 1440, longitude: 2880)> Size: 17MB
[4147200 values with dtype=float32]
Coordinates:
    time           datetime64[ns] 8B ...
    step           timedelta64[ns] 8B ...
    isobaricInhPa  float64 8B ...
  * latitude       (latitude) float64 12kB 89.94 89.81 89.69 ... -89.81 -89.94
  * longitude      (longitude) float64 23kB 0.0 0.125 0.25 ... 359.6 359.8 359.9
    valid_time     datetime64[ns] 8B ...
Attributes: (12/32)
    GRIB_paramId:                             130
    GRIB_dataType:                            fc
    GRIB_numberOfPoints:                      4147200
    GRIB_typeOfLevel:                         isobaricInhPa
    GRIB_stepUnits:                           1
    GRIB_stepType:                            instant
    ...                                       ...
    GRIB_parameterNumber:                     0
    GRIB_shortName:                           t
    GRIB_units:                               K
    long_name:                                Temperature
    units:                                    K
    standard_name:                            air_temperature
```

## Examples

See [cemc-data-guide](https://github.com/perillaroc/cemc-data-guide) project for more examples.

## LICENSE

Copyright &copy; 2020-2025, developers at cemc-oper.

`reki` is licensed under [Apache License, Version 2.0](./LICENSE)