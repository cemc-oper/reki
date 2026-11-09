# reki

[![Maturity-Emerging](https://img.shields.io/badge/Maturity-Emerging-A259FF)](https://github.com/cemc-oper/reki)
[![GitHub Release](https://img.shields.io/github/v/release/cemc-oper/reki)](https://github.com/cemc-oper/reki/releases)
[![PyPI - Version](https://img.shields.io/pypi/v/reki)](https://pypi.org/project/reki/)
[![GitHub License](https://img.shields.io/github/license/cemc-oper/reki)](https://github.com/cemc-oper/reki/blob/main/LICENSE)
[![GitHub Action Workflow Status](https://github.com/cemc-oper/reki/actions/workflows/ci.yaml/badge.svg)](https://github.com/cemc-oper/reki/actions/workflows/ci.yaml)

`reki` is a Python library for locating, reading, querying, and processing meteorological data. 
It provides a uniform source and query interface over GRIB2 data.
GRIB2 fields are decoded with ecCodes and returned as `xarray.DataArray` objects.
Support for other data formats, including NetCDF, GrADS, tabular data, and in-memory data, is currently under development

## Features

- Resolve operational file paths from versioned YAML templates.
- Read GRIB2 from local-file and URL sources.
- Select fields through a consistent query interface.
- Select original messages by their ecCodes keys and preserve decoded values and missing cells.
- Return decoded fields as `xarray.DataArray` objects for use with the Python scientific ecosystem.
- Provide common grid operations, including region extraction, point sampling, and interpolation.

## Installation

Python 3.11 or later is required.

```bash
pip install reki
```

Reading GRIB2 data requires ecCodes. 
Install it with your system package manager or install with pip/conda:

```bash
# use pip
pip install eccodeslib
# or using conda/mamba
conda install -c conda-forge eccodes
```

## CMADaaS-mounted data source

> [!note]
> This README uses a CMADaaS-mounted directory as its real-data example.
> Please run CMADaaS app before running any code.

reki includes local-path templates for CMADaaS-mounted GRIB data. 
Set `data_class="cmadaas"` and point `storage_base` at the mount root, commonly `/CMADAAS`.
The templates then resolve the system-specific directory and file name from the start time and forecast time.

The following data types currently have CMADaaS mount templates:

| Data type | Product |
| --- | --- |
| `cma_gfs_gmf/grib2/orig` | CMA-GFS |
| `cma_meso_3km/grib2/orig` | CMA-MESO 3km (V5.1)|
| `cma_meso_1km/grib2/orig` | CMA-MESO 1km (V6.1)|
| `cma_tym/grib2/orig` | CMA-TYM |
| `cma_geps/grib2/orig` | CMA-GEPS |
| `cma_reps/grib2/orig` | CMA-REPS |

## Quick start

```python
from reki import from_source

with from_source({"kind": "file", "path": "original.grib2"}) as source:
    field = source.sel(native={"grib": {
        "discipline": 0,
        "parameterCategory": 0,
        "parameterNumber": 0,
        "typeOfFirstFixedSurface": 103,
        "scaleFactorOfFirstFixedSurface": 0,
        "scaledValueOfFirstFixedSurface": 2,
    }}).one()
    data = field.to_xarray(rename="original")
    native_keys = field.metadata["native_fields"]
```

For a mounted CEMC original product, use `{"kind": "local", "dataset": "cma_gfs_gmf", "root": "/CMADAAS"}` and include the reference `time`. The dataset registration contains the file layout. Omitted lead or member selectors discover matching files in the layout. Use native keys to distinguish encodings within those files.

`one()` requires a unique original message. `all()` returns each matching field in source order. Assemble fields on a compatible grid with `to_xarray()`; inspect individual fields when grids differ. Original scalar metadata is available from each Field. Legacy message readers still accept an ecCodes shortName, a native key mapping or a record count.

See [native field queries](doc/source/guide/public-query.md).

## CMADaaS public queries

The optional `reki[cmadaas]` dependency supports named scalar grid requests through the shared source API. The default v33 catalog binds twelve CEMC services verified in task 07B, with one `cedarkit.t2m` mapping per service and four historical GFS surface cases. Configure the MUSIC connection in CedarKit YAML and use `from_source({"kind": "cmadaas", "dataset": "cma_gfs_gmf_cmadaas"})`. See [the service query guide](doc/source/guide/cmadaas-query.md) for accepted samples, response contracts and unit provenance. The task 07A offline candidate remains explicitly selectable for replay.

## Protected reading functions

The ordinary `reki.format.grib.load_field_from_file` and ecCodes `reki.readers.grib.eccodes.load_field_from_file` retain first-match scalar selection, file-order level lists, native names/units/coordinates, and lazy value access. A missing match, including an empty requested level list, returns `None`. Historical `start_time`, `forecast_time`, and `valid_time` arguments remain header predicates. Returned ecCodes handles belong to the caller and must be released; `count` is a one-based physical message number and overrides filters. Byte readers preserve the original message bytes.

`load_field_from_files` returns a single-variable DataArray or `None`; `load_fields_from_file` returns a Dataset, including an empty Dataset on no match. These collection functions use the public v1 coordinate organization, duplicate/grid checks and `cedarkit_query_report`. For collections, `level=None` or `"all"` imposes no level restriction; `level_dim` and `lazy=True` are unsupported. Only a single variable may be renamed by `field_name`. An empty file list is invalid. Legacy filters not expressible in the public Query schema remain adapter predicates and are recorded in the report's adapter provenance (`grib.legacy;selection=...`), alongside the expressible native Query criteria. They do not introduce another public query language.

The cfgrib backend, its named import paths and dependency have been removed. Explicit `engine="cfgrib"` raises `QueryError(code="unsupported")`. Protected GRIB functions accept `with_index=True` or a path string only to emit one caller-facing `FutureWarning`; they never inspect, read or write that index. `False` is quiet. Public queries do not use indexes.

NetCDF readers retain xarray lazy storage and close callbacks; missing variables/levels raise `QueryError(code="no_match")`, while an absent explicitly named coordinate raises `invalid_query`. GrADS readers retain eager/lazy selection and return `None` on no match. GrADS forecast coordinates reflect the CTL record's valid time relative to the start time inferred from supported operational filenames. I/O and decoding failures within owned reads use the public `SourceError` codes.

Old root `SourceSpec`, `FieldQuery`, `FieldMetadata`, `FieldList`, legacy exception classes, `one_or_none`, and positional `from_source("file", ...)` are retired. Use public mapping declarations with `reki.from_source`, public Query/Request objects, and `QueryError` / `SourceError`. Internal format/plugin records are private implementation details. The legacy source-exploration CLI is separate from the public Request CLI; historical Request CLI equivalence checks remain tracked separately.
