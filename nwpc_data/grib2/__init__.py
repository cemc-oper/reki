from pathlib import Path
import typing

import xarray as xr
import cfgrib


def load_field_from_file(
        file_path: str or Path,
        param: str or typing.Dict,
        level_type: str or int,
        level: int,
) -> xr.DataArray or None:
    """
    Load **one** field from GRIB2 file.

    This function will load the first variable fitting searching conditions.

    Parameters
    ----------
    file_path: str or Path
        GRIB2 file path
    param: str or typing.Dict
        parameter identifier. support two types:
        - str: parameter name, see shortName key using grib_ls of ecCodes.
        - typing.Dict: parameter keys, including:
            - discipline
            - parameterCategory
            - parameterNumber
    level_type: str or int
        level type, see typeOfLevel key using grib_ls of ecCodes.
    level: int
        level value.

    Returns
    -------
    xr.DataArray or None:
        `xr.DataArray` if found one file, or None if not.

    Examples
    --------
    Read 850hPa temperature from a GRAEPS GFS grib2 file.
    >>> load_field_from_file(
   ...     file_path="/g1/COMMONDATA/OPER/NWPC/GRAPES_GFS_GMF/Prod-grib/2020031721/ORIG/gmf.gra.2020031800105.grb2",
   ...     param="t",
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

    Load a filed without shortName.
    >>> load_field_from_file(
    ...     file_path="/g1/COMMONDATA/OPER/NWPC/GRAPES_GFS_GMF/Prod-grib/2020031721/ORIG/gmf.gra.2020031800105.grb2",
    ...     param={
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


    """
    filter_by_keys = {}
    read_keys = []
    if isinstance(param, str):
        filter_by_keys["shortName"] = param
    elif isinstance(param, typing.Dict):
        filter_by_keys.update(param)
        read_keys.extend(param.keys())
    else:
        raise ValueError(f"param is not supported: {param}")

    filter_by_keys.update({
        "typeOfLevel": level_type,
        "level": level,
    })

    backend_kwargs = {
        "indexpath": "",
        "filter_by_keys": filter_by_keys
    }
    if len(read_keys) > 0:
        backend_kwargs["read_keys"] = read_keys

    data_set = xr.open_dataset(
        file_path,
        engine="cfgrib",
        backend_kwargs=backend_kwargs
    )
    if data_set is None:
        return None
    return data_set[list(data_set.data_vars)[0]]
