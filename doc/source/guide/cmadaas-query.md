# Query CMADaaS MUSIC

Use a `cmadaas` source with a dataset ID to request fields from a MUSIC
service. The {doc}`public-query` guide covers files in a mounted archive.

## Install and configure

Install the `cmadaas` extra for the reki version covered by this guide.
From a source checkout, run the following command in your Python environment.

```bash
python -m pip install '.[cmadaas]'
```

The extra installs the `nuwe-cmadaas` client. Save your MUSIC credentials
and server settings in the `cmadaas` section of a CedarKit YAML file.
The example uses `cedarkit.yaml` in the working directory. Pass the path
to your file as `config` in the source declaration.

```yaml
cmadaas:
  auth:
    user: YOUR_USER
    password: YOUR_PASSWORD
  server:
    music_server: music.example.org
    music_port: 80
    music_ServiceId: 0
    music_connTimeout: 10
    music_readTimeout: 60
```

## Read a field

This example selects the GFS 2 m air temperature. Use a UTC reference time
and an ISO 8601 forecast lead for a field available to your account.

```python
from reki import from_source

source_options = {
    "kind": "cmadaas",
    "dataset": "cma_gfs_gmf_cmadaas",
    "config": "cedarkit.yaml",
}
with from_source(source_options) as source:
    selection = source.sel(
        parameter="cedarkit.t2m",
        time="2026-08-30T00:00:00Z",
        step="PT6H",
    )
    explanation = selection.explain()
    field = selection.one()
    data = field.to_xarray()
    report = field.report
```

`explain()` inspects the request mapping without contacting MUSIC.
Calling `one()` executes the request and requires one matching field.
`to_xarray()` returns the data on the service grid. See {doc}`query-cli` for
running the same queries from a JSON or YAML Request.

## Choose a dataset

The bundled catalog provides the following MUSIC datasets.

| Product | Analysis or control | Forecast or perturbation |
| --- | --- | --- |
| GFS | `cma_gfs_gmf_analysis_cmadaas` | `cma_gfs_gmf_cmadaas` |
| MESO-1KM | `cma_meso_1km_analysis_cmadaas` | `cma_meso_1km_forecast_cmadaas` |
| MESO-3KM | `cma_meso_3km_analysis_cmadaas` | `cma_meso_3km_forecast_cmadaas` |
| TYM | `cma_tym_analysis_cmadaas` | `cma_tym_forecast_cmadaas` |
| GEPS | `cma_geps_control_cmadaas` | `cma_geps_perturbation_cmadaas` |
| REPS | `cma_reps_control_cmadaas` | `cma_reps_perturbation_cmadaas` |

Use `step="PT0S"` for analysis and supply the member for an ensemble query.
Use `member=0` for a control member. For a pressure field, specify the
vertical identity, for example `level_type="pressure", level=850,`
`level_unit="hPa"`.

## Check availability and output

Supported parameters, levels, leads, members, and geographic coverage depend
on the dataset mapping. Use `selection.explain()` to inspect a mapping before
reading. Use `field.metadata` for the returned grid and source unit
information. An empty grid yields no field, and a grid filled with missing
values remains a field. Connection, authentication, and service failures
are reported as `SourceError`.

The report describes matching and completeness. If an independent expected
domain is unavailable, the report shows `unchecked` with
`expected_set_unknown`. Pass `completeness="required"` to `one()` or `all()`
when your workflow requires a check against an independent domain. To save
the report with the result, use `field.to_xarray(include_report=True)`.
See {doc}`grib/xarray-output` for the report attribute.
