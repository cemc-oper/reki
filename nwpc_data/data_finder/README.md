# data finder

Find data file from different paths listed in config files.

Data files will be copied or moved into different directories during different stages.
Function `find_local_file` finds some file in a path list where the actual file may be located.
This function checks each path item, and returns the file path until an existing file is found.
If none of these paths exists, `None` is returned. 

## Usage

Find an existing orig GRIB2 file of GRAPES GFS.

```pycon
>>> from nwpc_data.data_finder import find_local_file
>>> find_local_file(
...     "grapes_gfs_gmf/grib2/orig",
...     start_time="2020032100",
...     forecast_time="3h",
... )
/g1/COMMONDATA/OPER/NWPC/GRAPES_GFS_GMF/Prod-grib/2020032021/ORIG/gmf.gra.2020032100003.grb2
```

Find a non-existing orig GRIB2 file of GRAPES GFS.

```pycon
>>> find_local_file(
...     "grapes_gfs_gmf/grib2/orig",
...     start_time="2020032100",
...     forecast_time="1h",
... )
None
```

Find a grib2 file in storage for GRAPES MESO 3km.

```pycon
>>> find_local_file(
...     "grapes_meso_3km/grib2/orig",
...     start_time="2020032100",
...     forecast_time="1h",
...     data_level="storage",
... )
/sstorage1/COMMONDATA/OPER/NWPC/GRAPES_MESO_3KM/Prod-grib/2020032021/ORIG/rmf.hgra.2020032100001.grb2
```

## Config

An example config file is as follows:

```yaml
file_name: gmf.gra.{{ time_vars.Year }}{{ time_vars.Month }}{{ time_vars.Day }}{{ time_vars.Hour }}{{ time_vars.Forecast }}.grb2

paths:
  - type: local
    level: runtime
    path: /g2/nwp_pd/NWP_PST_DATA/GMF_GRAPES_GFS_POST/togrib2/output_togrib2/{{ time_vars.Year }}{{ time_vars.Month }}{{ time_vars.Day }}{{ time_vars.Hour }}

  - type: local
    level: archive
    path: /g1/COMMONDATA/OPER/NWPC/GRAPES_GFS_GMF/Prod-grib/{{ time_vars.Year4DV }}{{ time_vars.Month4DV }}{{ time_vars.Day4DV }}{{ time_vars.Hour4DV }}/ORIG

  - type: local
    level: storage
    path: /sstorage1/COMMONDATA/OPER/NWPC/GRAPES_GFS_GMF/Prod-grib/{{ time_vars.Year4DV }}{{ time_vars.Month4DV }}{{ time_vars.Day4DV }}{{ time_vars.Hour4DV }}/ORIG
```

`file_name` and `path` in `paths` are Jinja2 templates using variable `time_vars`.

Embedded config files are in `conf` directory. 
Please use them if you are in CMA-PI HPC.

## Related projects

Please visit [nwpc-oper/nwpc-data-client](https://github.com/nwpc-oper/nwpc-data-client) project.

## License

`data_finder` is part of [nwpc-oper/nwpc-data](https://github.com/nwpc-oper/nwpc-data) project.