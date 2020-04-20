# nwpc-data

Load GRIB2 data using [eccodes-python](https://github.com/ecmwf/eccodes-python)
or [cfgrib](https://github.com/ecmwf/cfgrib).

## Installation

Download the latest source code from GitHub and install using `pip`.

If you are using system python, such as apps/python/3.6.3/gnu on HPC CMA-PI,
please use `--user` option to install on user directory.

`nwpc-data` uses ecCodes to decode GRIB files
(which is needed by [eccodes-python](https://github.com/ecmwf/eccodes-python) and [cfgrib](https://github.com/ecmwf/cfgrib)). 
Please install ecCodes through conda or other package source.

## Getting started

`nwpc-data` has several functions to help users to find one filed from a local GRIB 2 file.

`load_message_from_file` from `nwpc_data.grib.eccodes` returns a GRIB handler.
Users can use it to get attrs or values with functions from [eccodes-python](https://github.com/ecmwf/eccodes-python) .

For example, load 850hPa temperature from GRAPES GFS and get values from the returned message.

```pycon
>>> from nwpc_data.grib.eccodes import load_message_from_file
>>> t = load_message_from_file(
...     file_path="/g1/COMMONDATA/OPER/NWPC/GRAPES_GFS_GMF/Prod-grib/2020031721/ORIG/gmf.gra.2020031800105.grb2",
...     parameter="t",
...     level_type="isobaricInhPa",
...     level=850,
... )
>>> data = eccodes.codes_get_double_array(t, "values")
>>> data = data.reshape([720, 1440])
>>> data
array([[249.19234375, 249.16234375, 249.16234375, ..., 249.15234375,
    249.19234375, 249.14234375],
   [249.45234375, 249.45234375, 249.42234375, ..., 249.45234375,
    249.44234375, 249.44234375],
   [249.69234375, 249.68234375, 249.68234375, ..., 249.70234375,
    249.67234375, 249.68234375],
   ...,
   [235.33234375, 235.45234375, 235.62234375, ..., 235.47234375,
    235.63234375, 235.48234375],
   [235.78234375, 235.91234375, 235.64234375, ..., 235.80234375,
    235.72234375, 235.82234375],
   [235.66234375, 235.86234375, 235.82234375, ..., 235.85234375,
    235.68234375, 235.70234375]])
```

**NOTE**: Please release the handler using `eccodes.codes_release` manually.

`eccodes` engine also provides some functions to load array from GRIB2 file
in which GRIB2 message is loaded by [eccodes-python](https://github.com/ecmwf/eccodes-python)
and converted into `xarray.DataArray` by `nwpc-data`.

**WARNING**: This feature is under construction.

```pycon
>>> from nwpc_data.grib.eccodes import load_field_from_file
>>> load_field_from_file(
...     file_path="/sstorage1/COMMONDATA/OPER/NWPC/GRAPES_GFS_GMF/Prod-grib/2020031721/ORIG/gmf.gra.2020031800105.grb2",
...     parameter="t",
...     level_type="isobaricInhPa",
...     level=850,
... )
<xarray.DataArray 't' (latitude: 720, longitude: 1440)>
array([[249.19234375, 249.16234375, 249.16234375, ..., 249.15234375,
        249.19234375, 249.14234375],
       [249.45234375, 249.45234375, 249.42234375, ..., 249.45234375,
        249.44234375, 249.44234375],
       [249.69234375, 249.68234375, 249.68234375, ..., 249.70234375,
        249.67234375, 249.68234375],
       ...,
       [235.33234375, 235.45234375, 235.62234375, ..., 235.47234375,
        235.63234375, 235.48234375],
       [235.78234375, 235.91234375, 235.64234375, ..., 235.80234375,
        235.72234375, 235.82234375],
       [235.66234375, 235.86234375, 235.82234375, ..., 235.85234375,
        235.68234375, 235.70234375]])
Coordinates:
    time           datetime64[ns] 2020-03-18
    step           timedelta64[ns] 4 days 09:00:00
    valid_time     datetime64[ns] 2020-03-22T09:00:00
    isobaricInhPa  int64 850
  * latitude       (latitude) float64 89.88 89.62 89.38 ... -89.38 -89.62 -89.88
  * longitude      (longitude) float64 0.0 0.25 0.5 0.75 ... 359.2 359.5 359.8
Attributes:
    GRIB_edition:                    2
    GRIB_centre:                     babj
    GRIB_subCentre:                  0
    GRIB_tablesVersion:              4
    GRIB_localTablesVersion:         1
    GRIB_dataType:                   fc
    GRIB_dataDate:                   20200318
    GRIB_dataTime:                   0
    GRIB_validityDate:               20200322
    GRIB_validityTime:               900
    GRIB_step:                       105
    GRIB_stepType:                   instant
    GRIB_stepUnits:                  1
    GRIB_stepRange:                  105
    GRIB_endStep:                    105
    GRIB_name:                       Temperature
    GRIB_shortName:                  t
    GRIB_cfName:                     air_temperature
    GRIB_discipline:                 0
    GRIB_parameterCategory:          0
    GRIB_parameterNumber:            0
    GRIB_gridType:                   regular_ll
    GRIB_gridDefinitionDescription:  Latitude/longitude 
    GRIB_typeOfFirstFixedSurface:    pl
    GRIB_typeOfLevel:                isobaricInhPa
    GRIB_level:                      850
    GRIB_numberOfPoints:             1036800
    GRIB_missingValue:               9999
    GRIB_units:                      K
    long_name:                       Temperature
    units:                           K
```

## Engines

`nwpc-data` loads GRIB2 file using `eccodes` by default and also supports `cfgrib`.

### cfgrib

If you don't care about loading speed, please use [cfgrib](https://github.com/ecmwf/cfgrib) engine
with option `engine="cfgrib"`.

Please install cfgrib before using this engine.

Read 850hPa temperature from a GRAEPS GFS grib2 file using `shortName` key `t`.
( `shortName` is an ecCodes key. )

```pycon
>>> load_field_from_file(
...     file_path="/g1/COMMONDATA/OPER/NWPC/GRAPES_GFS_GMF/Prod-grib/2020031721/ORIG/gmf.gra.2020031800105.grb2",
...     parameter="t",
...     level_type="isobaricInhPa",
...     level=850,
...     engine="cfgrib",
... )
<xarray.DataArray 't' (latitude: 720, longitude: 1440)>
[1036800 values with dtype=float32]
Coordinates:
    time           datetime64[ns] ...
    step           timedelta64[ns] ...
    isobaricInhPa  int64 ...
  * latitude       (latitude) float64 89.88 89.62 89.38 ... -89.38 -89.62 -89.88
  * longitude      (longitude) float64 0.0 0.25 0.5 0.75 ... 359.2 359.5 359.8
    valid_time     datetime64[ns] ...
Attributes:
    GRIB_paramId:                             130
    GRIB_shortName:                           t
    GRIB_units:                               K
    GRIB_name:                                Temperature
    GRIB_cfName:                              air_temperature
    GRIB_cfVarName:                           t
    GRIB_dataType:                            fc
    GRIB_missingValue:                        9999
    GRIB_numberOfPoints:                      1036800
    GRIB_typeOfLevel:                         isobaricInhPa
    GRIB_NV:                                  0
    GRIB_stepUnits:                           1
    GRIB_stepType:                            instant
    GRIB_gridType:                            regular_ll
    GRIB_gridDefinitionDescription:           Latitude/longitude
    GRIB_Nx:                                  1440
    GRIB_iDirectionIncrementInDegrees:        0.25
    GRIB_iScansNegatively:                    0
    GRIB_longitudeOfFirstGridPointInDegrees:  0.0
    GRIB_longitudeOfLastGridPointInDegrees:   359.75
    GRIB_Ny:                                  720
    GRIB_jDirectionIncrementInDegrees:        0.25
    GRIB_jPointsAreConsecutive:               0
    GRIB_jScansPositively:                    0
    GRIB_latitudeOfFirstGridPointInDegrees:   89.875
    GRIB_latitudeOfLastGridPointInDegrees:    -89.875
    long_name:                                Temperature
    units:                                    K
    standard_name:                            air_temperature
```

If the field doesn't have a `shortName`, use `dict` for `parameter`.

Load a filed without shortName.

```pycon
>>> load_field_from_file(
...     file_path="/g1/COMMONDATA/OPER/NWPC/GRAPES_GFS_GMF/Prod-grib/2020031721/ORIG/gmf.gra.2020031800105.grb2",
...     parameter={
...         "discipline": 0,
...         "parameterCategory": 2,
...         "parameterNumber": 225,
...     },
...     level_type="isobaricInhPa",
...     level=850,
... )
<xarray.DataArray 'paramId_0' (latitude: 720, longitude: 1440)>
[1036800 values with dtype=float32]
Coordinates:
    time           datetime64[ns] ...
    step           timedelta64[ns] ...
    isobaricInhPa  int64 ...
  * latitude       (latitude) float64 89.88 89.62 89.38 ... -89.38 -89.62 -89.88
  * longitude      (longitude) float64 0.0 0.25 0.5 0.75 ... 359.2 359.5 359.8
    valid_time     datetime64[ns] ...
Attributes:
    GRIB_paramId:                             0
    GRIB_dataType:                            fc
    GRIB_missingValue:                        9999
    GRIB_numberOfPoints:                      1036800
    GRIB_typeOfLevel:                         isobaricInhPa
    GRIB_NV:                                  0
    GRIB_stepUnits:                           1
    GRIB_stepType:                            instant
    GRIB_gridType:                            regular_ll
    GRIB_gridDefinitionDescription:           Latitude/longitude
    GRIB_Nx:                                  1440
    GRIB_iDirectionIncrementInDegrees:        0.25
    GRIB_iScansNegatively:                    0
    GRIB_longitudeOfFirstGridPointInDegrees:  0.0
    GRIB_longitudeOfLastGridPointInDegrees:   359.75
    GRIB_Ny:                                  720
    GRIB_jDirectionIncrementInDegrees:        0.25
    GRIB_jPointsAreConsecutive:               0
    GRIB_jScansPositively:                    0
    GRIB_latitudeOfFirstGridPointInDegrees:   89.875
    GRIB_latitudeOfLastGridPointInDegrees:    -89.875
    GRIB_discipline:                          0
    GRIB_parameterCategory:                   2
    GRIB_parameterNumber:                     225
    long_name:                                original GRIB paramId: 0
    units:                                    1
```

## Examples

See `example` directory for more examples.

## LICENSE

Copyright &copy; 2020, developers at nwpc-oper.

`nwpc-data` is licensed under [GPL v3.0](LICENSE.md)