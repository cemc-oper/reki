# reki

[![GitHub Release](https://img.shields.io/github/v/release/cemc-oper/reki)](https://github.com/cemc-oper/reki/releases)
[![PyPI](https://img.shields.io/pypi/v/reki)](https://pypi.org/project/reki/)
[![CI](https://github.com/cemc-oper/reki/actions/workflows/ci.yaml/badge.svg)](https://github.com/cemc-oper/reki/actions/workflows/ci.yaml)
[![License](https://img.shields.io/github/license/cemc-oper/reki)](https://github.com/cemc-oper/reki/blob/main/LICENSE)

`reki` is a Python library for finding, reading, and processing meteorological
data. It decodes GRIB2 messages with ecCodes and converts selected fields to
xarray datasets.

## Features

- Find data in local and mounted archives using path templates, and download files from URLs.
- Select GRIB2 fields by parameter name, level, reference time, forecast lead, or encoded GRIB keys.
- Read NetCDF, GrADS, and tabular data with format-specific readers.
- Extract regions, sample points, and interpolate gridded data.

### Data sources

| `kind` | Use case |
| --- | --- |
| `file` | Read a local GRIB2 file at a known path. |
| `local` | Find and read GRIB2 files in a mounted archive using a dataset ID and mount root. |
| `cmadaas` | Query CMADaaS MUSIC using a dataset ID and a CedarKit YAML file with connection settings and credentials. |

## Installation

reki requires Python 3.11 or newer. Install a release from PyPI.

```bash
python -m pip install reki
```

To use the API shown below from a checkout, run `python -m pip install .`
from the repository root.

Install `reki[cmadaas]` for CMADaaS MUSIC access or `reki[lazy]` for
Dask-backed arrays in supported readers.

## Quick start

Read 2 m air temperature from a local GRIB2 file with one matching field.
For a public ECMWF IFS example, run `reki-test-data download ecmwf_ifs` and
replace `forecast.grib2` with the downloaded file path.

```python
from reki import from_source

with from_source({"kind": "file", "path": "forecast.grib2"}) as source:
    temperature = source.sel(parameter="t2m").one().to_xarray()["t2m"]

print(temperature)
```

With the ECMWF IFS sample, the output is an `xarray.DataArray` named `t2m`
with `units` set to `K` (kelvin).

## Documentation

[中文文档](https://reki.readthedocs.io/)

## Contributing

Report bugs or request features on [GitHub Issues](https://github.com/cemc-oper/reki/issues).

## License

`reki` is licensed under the
[Apache License 2.0](https://github.com/cemc-oper/reki/blob/main/LICENSE).
