# reki

![Maturity-Emerging](https://img.shields.io/badge/Maturity-Emerging-A259FF)
![GitHub Release](https://img.shields.io/github/v/release/cemc-oper/reki)
![PyPI - Version](https://img.shields.io/pypi/v/reki)
![GitHub License](https://img.shields.io/github/license/cemc-oper/reki)
![GitHub Action Workflow Status](https://github.com/cemc-oper/reki/actions/workflows/ci.yaml/badge.svg)

`reki` is a Python library for locating, reading, querying, and processing
meteorological data. It provides a uniform source and query interface over
GRIB2, NetCDF, GrADS, tables, and in-memory data. GRIB2 fields are decoded with
ecCodes or cfgrib and returned as `xarray.DataArray` objects.

This README uses a CMADaaS-mounted GRIB directory as its real-data example.
The mounted directory is a local file source; it is distinct from the CMADaaS
remote service and does not require CMADaaS credentials.

## Features

- Resolve operational file paths from versioned YAML templates.
- Read GRIB2, NetCDF, GrADS, table, URL, memory, and local-file sources.
- Select fields through a consistent query interface.
- Resolve stable parameter identifiers and external parameter names.
- Return decoded fields as `xarray.DataArray` objects for use with the Python
  scientific ecosystem.
- Provide common grid operations, including region extraction, point sampling,
  and interpolation.

## Installation

Python 3.11 or later is required.

```bash
pip install reki
```

For development in this workspace:

```bash
cd repo/reki
uv sync --group test
pytest -m "not needs_data and not cma_hpc and not cmadaas_local and not cmadaas_service"
```

Reading GRIB2 data requires ecCodes. Install it with your system package
manager or, for conda environments:

```bash
conda install -c conda-forge eccodes
```

## CMADaaS-mounted data source

reki includes local-path templates for CMADaaS-mounted GRIB data. Set
`data_class="cmadaas"` and point `storage_base` at the mount root, commonly
`/CMADAAS`. The templates then resolve the system-specific directory and file
name from the start time and forecast time.

The following data types currently have CMADaaS mount templates:

| Data type | Product |
| --- | --- |
| `cma_gfs_gmf/grib2/orig` | CMA-GFS global forecast |
| `cma_meso_3km/grib2/orig` | CMA-MESO 3 km forecast |
| `cma_meso_1km/grib2/orig` | CMA-MESO 1 km forecast |
| `cma_tym/grib2/orig` | CMA-TYM forecast |
| `cma_geps/grib2/orig` | CMA-GEPS ensemble forecast |
| `cma_reps/grib2/orig` | CMA-REPS ensemble forecast |

## Quick start

### Read a field directly from the mount

Use `from_source("local", ...)` to resolve the file and open it in one step.
The example reads CMA-GFS 2 m temperature from the CMADaaS mount:

```python
import reki

reader = reki.from_source(
    "local",
    "cma_gfs_gmf/grib2/orig",
    start_time="2025081900",
    forecast_time="24h",
    data_class="cmadaas",
    storage_base="/CMADAAS",
)

t2m = reader.sel(
    parameter="2t",
    level_type="heightAboveGround",
    level=2,
).first().to_xarray()

print(t2m.name, t2m.shape)
```

`sel()` narrows the field list without decoding the GRIB values. Calling
`first()` selects the first matching field, and `to_xarray()` decodes it to an
`xarray.DataArray`.

### Resolve the file path first

When an application needs the path for logging, validation, or another GRIB
tool, call `find_local_file()` directly:

```python
from reki.data_finder import find_local_file

path = find_local_file(
    "cma_gfs_gmf/grib2/orig",
    start_time="2025081900",
    forecast_time="24h",
    data_class="cmadaas",
    storage_base="/CMADAAS",
)

print(path)
# /CMADAAS/DATA/NAFP/NMC/GRAPES-GFS-GLB/2025/20250819/Z_NAFP_C_BABJ_20250819000000_P_NWPC-GRAPES-GFS-GLB-02400.grib2
```

For ensemble data, add the member number used by the template:

```python
path = find_local_file(
    "cma_geps/grib2/orig",
    start_time="2025081900",
    forecast_time="24h",
    number=2,
    data_class="cmadaas",
    storage_base="/CMADAAS",
)
```

## Querying fields

Use GRIB keys in `sel()` to identify a field. The common keys are `parameter`,
`level_type`, and `level`; additional GRIB keys can be supplied when a product
needs more specific filtering.

```python
temperature_850 = reader.sel(
    parameter="t",
    level_type="pl",
    level=850,
).first().to_xarray()

reflectivity_850 = reader.sel(
    parameter={
        "discipline": 0,
        "parameterCategory": 16,
        "parameterNumber": 225,
    },
    level_type="pl",
    level=850,
).first().to_xarray()
```

Use `one()` instead of `first()` when exactly one match is required. It raises
an error if the query is ambiguous, which is useful in production workflows.

## Working with xarray data

The decoded result is a regular `xarray.DataArray`, including spatial and time
coordinates. Standard xarray operations work directly:

```python
from reki.operator import extract_region

east_asia_t2m = extract_region(
    t2m,
    start_longitude=105,
    end_longitude=125,
    start_latitude=25,
    end_latitude=45,
)

mean_temperature = float(east_asia_t2m.mean())
```

## Source model

The public source flow is intentionally small:

```text
source configuration → source → reader → field query → xarray.DataArray
```

- A **source** identifies where data comes from, such as a local mount, file,
  URL, memory object, or remote service.
- A **reader** understands the source format and exposes a field list.
- A **field query** selects metadata without reading all field values.
- `to_xarray()` decodes the selected field only when its values are needed.

This separation lets the same query-oriented application code work across
different file locations and supported source types.

## License

Copyright &copy; 2020-2026, developers at CMA Earth System Modeling And
Prediction Centre.

`reki` is licensed under the [Apache License 2.0](LICENSE).
