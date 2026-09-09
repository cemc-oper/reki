# data finder

Find data file from different paths listed in config files.

Data files will be copied or moved into different directories during different stages.
Function `find_local_file` finds some file in a path list where the actual file may be located.
This function checks each path item, and returns the file path until an existing file is found.
If none of these paths exists, `None` is returned. 

## Usage

Find an existing orig GRIB2 file of GRAPES GFS.

```pycon
>>> from reki.data_finder import find_local_file
>>> find_local_file(
...     "cma_gfs_gmf/grib2/orig",
...     start_time="2020032100",
...     forecast_time="3h",
... )
/g1/COMMONDATA/OPER/NWPC/GRAPES_GFS_GMF/Prod-grib/2020032021/ORIG/gmf.gra.2020032100003.grb2
```

Find a non-existing orig GRIB2 file of GRAPES GFS.

```pycon
>>> find_local_file(
...     "cma_gfs_gmf/grib2/orig",
...     start_time="2020032100",
...     forecast_time="1h",
... )
None
```

Find a grib2 file in storage for GRAPES MESO 3km.

```pycon
>>> find_local_file(
...     "cma_meso_3km/grib2/orig",
...     start_time="2020032100",
...     forecast_time="1h",
...     data_level="storage",
... )
/sstorage1/COMMONDATA/OPER/NWPC/GRAPES_MESO_3KM/Prod-grib/2020032021/ORIG/rmf.hgra.2020032100001.grb2
```

Find a grib2 file for member 1 of GRAPES GEPS using `number=1`.

```pycon
>>> find_local_file(
...     "cma_geps/grib2/orig",
...     start_time="2020032100",
...     forecast_time="3h",
...     data_level="storage",
...     number=1,
... )
/sstorage1/COMMONDATA/OPER/NWPC/GRAPES_GEPS/Prod-grib/2020032100/grib2/gef.gra.001.2020032100003.grb2
```

## Config

An example config file is as follows:

```yaml
query:
  system: cma_gfs_gmf
  stream: oper
  type: grib2
  name: orig

file_name: 'gmf.gra.{{ time_vars.Year }}{{ time_vars.Month }}{{ time_vars.Day }}{{ time_vars.Hour }}{{ time_vars.Forecast }}.grb2'

paths:
  - type: local
    level: runtime
    path: "/g0/nwp_pd/NWP_CMA_GFS_GMF_POST_DATA/{{ time_vars.Year }}{{ time_vars.Month }}{{ time_vars.Day }}{{ time_vars.Hour }}/data/output/grib2_orig/"

  - type: local
    level: archive
    path: '/g1/COMMONDATA/OPER/NWPC/GRAPES_GFS_GMF/Prod-grib/{{ time_vars.Year }}{{ time_vars.Month }}{{ time_vars.Day }}{{ time_vars.Hour }}/ORIG'

  - type: local
    level: storage
    path: '/sstorage1/COMMONDATA/OPER/NWPC/GRAPES_GFS_GMF/Prod-grib/{{ time_vars.Year }}{{ time_vars.Month }}{{ time_vars.Day }}{{ time_vars.Hour }}/ORIG'

  - type: local
    level: storage
    path: '{{ query_vars.storage_base }}/GRAPES_GFS_GMF/Prod-grib/{{ time_vars.Year }}{{ time_vars.Month }}{{ time_vars.Day }}{{ time_vars.Hour }}/ORIG'
```

`file_name` and `path` in `paths` are Jinja2 templates using variable `time_vars`.

If other parameters are needed, put them in `query_vars`.
For example, GRAPES GEPS needs member number to locate GRIB 2 file. `query_vars.number` is the member number.

```yaml
file_name: "gef.gra.{{ '%.3d' | format(query_vars.number) }}.{{ time_vars.Year }}{{ time_vars.Month }}{{ time_vars.Day }}{{ time_vars.Hour }}{{ time_vars.Forecast }}.grb2"
```

Embedded config files are in `conf` directory. 
Please use them if you are in CMA-PI HPC.

## Command Line Tool

Data finder also provides a module level CLI tool to find local files.

The following command: 

```shell script
python -m reki.data_finder local \
    --start-time "2020010100" \
    --forecast-time "3h" \
    --data-type="cma_geps/grib2/orig" \
    --data-level="storage" \
    --number=1
```

will print GRIB2 file path for GRAPES GEPS member 1.

```
/sstorage1/COMMONDATA/OPER/NWPC/GRAPES_GEPS/Prod-grib/2020010100/grib2/gef.gra.001.2020010100003.grb2
```

If required file is not found, command will print `None`.

## Related projects

Please visit [cemc-oper/nwpc-data-client](https://github.com/cemc-oper/nwpc-data-client) project.

## License

`data_finder` is part of [cemc-oper/reki](https://github.com/cemc-oper/reki) project.