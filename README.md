# nwpc-data

Load GRIB2 data using [cfgrib](https://github.com/ecmwf/cfgrib).

## Installation

Clone or download the latest source code from GitHub and install using `pip`:

```bash
pip install .
```

## Getting started

Loading one field from GRIB2 file using `nwpc_data.grib.load_field_from_file`.

Read 850hPa temperature from a GRAEPS GFS grib2 file using `shortName` key `t`.
( `shortName` is an ecCodes key. )

```pycon
>>> load_field_from_file(
...     file_path="/g1/COMMONDATA/OPER/NWPC/GRAPES_GFS_GMF/Prod-grib/2020031721/ORIG/gmf.gra.2020031800105.grb2",
...     parameter="t",
...     level_type="isobaricInhPa",
...     level=850,
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