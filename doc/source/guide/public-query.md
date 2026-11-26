# GRIB field queries

Use `reki.from_source()` to open a GRIB file or an archive. Select fields by
name for common meteorological quantities, or by native message keys for a
specific GRIB encoding.

## Named selection from a GRIB2 file

A file source with just a path uses the bundled parameter registry and
GRIB2 mappings. This example reads the 2 m air temperature from a file
containing one matching field.

```python
from reki import from_source

with from_source({"kind": "file", "path": "forecast.grib2"}) as source:
    field = source.sel(parameter="t2m").one()
    temperature = field.to_xarray()["t2m"]
```

`t2m`, `cedarkit.t2m`, and `2t` select the same field in kelvin. To narrow a
query, add selectors such as reference time, forecast lead, or level.
`first()` returns the first field or `None`. `one()` requires exactly one
match. `all()` returns the matching fields in source order.

For an 850 hPa temperature field, use
`source.sel(parameter="t", level_type="pressure", level=850, level_unit="hPa")`.
Python `sel()` also accepts the level type aliases `pl`, `sfc`, and `ml` in
keyword arguments and query mappings. In Query objects and JSON or YAML
Request documents, use `pressure`, `surface`, and `model_level`. See the
{doc}`grib/levels` guide.

### wgrib2 and ecCodes short names

For `file` and `local` sources, reki resolves a name in this order.

1. An exact CedarKit name, alias, or ID.
2. A short name in the bundled wgrib2 NCEP tables.
3. The ecCodes `shortName` of the record.

Use uppercase wgrib2 names and match the case of CedarKit and ecCodes names.
To choose a convention explicitly, prefix the name with `cedarkit:`,
`wgrib2:`, or `eccodes:`. For example, `wgrib2:APCP` selects by the wgrib2
short name. The bare name `APCP` uses the CedarKit accumulation definition.

## Select by native GRIB keys

Use `native.grib` to select a particular encoding, including fields outside
the bundled named mappings.

```python
with from_source({"kind": "file", "path": "forecast.grib2"}) as source:
    field = source.sel(native={"grib": {"shortName": "2t"}}).one()
    headers = field.metadata["native_fields"]
    temperature = field.to_xarray(rename="t2m")["t2m"]
```

Inspect `headers` to find keys such as `discipline`, `parameterCategory`,
`parameterNumber`, table version, and fixed-surface type. Combine the keys
needed to distinguish fields in local tables. Use `source.sel().all()` to
enumerate messages in file order. Each field carries its one-based ordinal,
byte offset, and encoded length in `field.metadata["source"]`.
`field.read_grib_message()` retrieves the original message bytes while the
source is open.

<a id="cemc-orig-support-in-catalog-v57"></a>

## Read CEMC ORIG files and archives

Use a dataset ID to select product-specific mappings. For a single file, add
`dataset` to the `file` declaration. For an archive, use `kind="local"` with
the mounted root, and supply the UTC reference time and forecast lead.

```python
with from_source({"kind": "local", "dataset": "cma_gfs_gmf", "root": "/CMADAAS"}) as source:
    field = source.sel(
        parameter="t2m", time="2026-11-02T12:00:00Z", step="PT6H"
    ).one()
    temperature = field.to_xarray()["t2m"]
```

Replace the root and time selectors with values for your archive. Supply a
member for an individual ensemble field. Product queries use the catalog's
member numbering. Supported standalone GRIB2 queries use the member number
encoded in the message. See {doc}`grib/ensemble`.

| Product | Dataset ID |
| --- | --- |
| GFS | `cma_gfs_gmf` |
| MESO-1KM | `cma_meso_1km` |
| MESO-3KM | `cma_meso_3km` |
| TYM | `cma_tym` |
| GEPS | `cma_geps` |
| REPS | `cma_reps` |

`reki.load_catalog()` loads the catalog bundled with the installed package.
To select an exported catalog, pass
`context={"catalog": {"path": "catalog-v1.json"}}` to `from_source()`.
The catalog resolves its parameter and mapping files relative to its
location. To override the standalone resources, provide both
`parameter_registry` and `mappings.grib2` in `context`.

## Inspect the result and query report

Use `selection.explain()` to inspect the selected mappings and predicates.
`field.report` gives the execution report. Pass `include_report=True` to
`to_xarray()` to attach it to the result. A file query without an independent
expected domain reports `unchecked` with `expected_set_unknown`. See
{doc}`grib/xarray-output` for the report attribute and output layout.

For named mappings with a unit rule, the result exposes the mapped `units`.
Raw-value mappings preserve decoded values and missing cells. Inspect
`field.metadata["native_fields"]` for the source encoding and decoder unit
metadata. For example, standalone CEMC `glw`, `gsw`, and `hfx` mappings
retain the encoded statistical interval and omit the output `units` attribute.

## Encoded value precision

For GRIB simple packing and lossless JPEG packing,
`field.metadata["value_encoding"]` records the bit count, scaling, and
quantization error bound in the decoded value's unit. The bound describes
packing precision. Constant fields have a zero bound.
