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
A public ECMWF IFS example is available in the
[sample data guide](https://reki.readthedocs.io/zh-cn/latest/quick-start/test-data.html).

```python
from reki import from_source

with from_source({"kind": "file", "path": "forecast.grib2"}) as source:
    temperature = source.sel(parameter="t2m").one().to_xarray()["t2m"]

print(temperature)
```

## Documentation

- [Documentation home](https://reki.readthedocs.io/)
- [Finding data](https://reki.readthedocs.io/zh-cn/latest/guide/finding/index.html)
- [Querying GRIB2 fields](https://reki.readthedocs.io/zh-cn/latest/guide/public-query.html)
- [Using CMADaaS MUSIC](https://reki.readthedocs.io/zh-cn/latest/guide/cmadaas-query.html)
- [Migrating from older versions](https://reki.readthedocs.io/zh-cn/latest/guide/migration.html)

## Contributing

Development setup is covered in the
[contributing guide](https://reki.readthedocs.io/zh-cn/latest/development/contributing.html).
Report bugs or request features on [GitHub Issues](https://github.com/cemc-oper/reki/issues).

## License

`reki` is licensed under the
[Apache License 2.0](https://github.com/cemc-oper/reki/blob/main/LICENSE).
