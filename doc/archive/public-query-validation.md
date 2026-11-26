# GRIB field queries

> Historical validation record preserved from reki `957e968`.
> [Current guide](../source/guide/public-query.md)

Open a GRIB file with `reki.from_source({"kind": "file", "path": path})`. Pass `native={"grib": {...}}` to `sel` using the encoded scalar keys of the intended record. For CEMC local tables, include centre, table version, parameter triple, PDT or fixed surface keys as needed. Use `Field.metadata["native_fields"]` to inspect the selected record.

`first()` returns the first match, `one()` requires one match and `all()` returns all matching fields. `to_xarray(rename="original")` gives a readable variable name for a single native field. Returned values follow the original scan order. Missing points follow GRIB packing and bitmap information. An unrecognized local parameter or fixed-surface code can still be selected by its encoded keys.

To enumerate every message in one file, use `source.sel().all()`. Each returned field has a one-based file ordinal, byte offset and encoded length in `field.metadata["source"]`. The fields are in file order, including repeated native keys at different offsets. While the source is open, call `field.read_grib_message()` on a field to retrieve its original bytes without decoding the values. This method also works on fields selected from `kind="local"`.

For an exported CEMC ORIG catalog, set the source's `dataset` and pass the catalog path in `context={"catalog": {"path": ...}}`. Use `source.sel(parameter="cldb").all()` to select cloud base by name. The catalog resolves the product's parameter and mapping files relative to its own location. A named GRIB mapping without a unit rule returns the original decoded values and their missingness. The returned field carries the encoded keys in `field.metadata["native_fields"]` and omits the standard `units` attribute. A vertical rule projects the encoded fixed surfaces into Query coordinates when the mapping declares that interpretation.

Local sources use dataset-specific file layouts. Supply the origin in UTC, and optionally the lead or file member. For multi-record queries, a successful scan is bounded by the selected files. Product-wide completeness requires its own independent domain.

For REPS, `kind="local"` prefers the archive directory for the origin's Beijing date. A matching file in the next Beijing-date directory fills an absent entry. Both directories use the requested UTC origin, lead and member in the filename.

## Named selection from a GRIB2 file

A file source with just a path uses reki's public parameter registry and generic GRIB2 mappings.

```python
from reki import from_source

with from_source({"kind": "file", "path": "forecast.grib2"}) as source:
    field = source.sel(parameter="t2m").one()
    temperature = field.to_xarray().t2m
```

`t2m`, `cedarkit.t2m` and `2t` select the same 2 m temperature field in K. The bundled registry defines 229 IDs, and 347 independent rules recognize 132 of them from GRIB2 headers. Each rule checks the relevant tables, template and field conditions per message. A named rule without a reviewed unit translation returns the original decoded values and retains the decoder's unit metadata in `Field.metadata["native_fields"]`.

Python `sel()` accepts `pl`, `sfc`, and `ml` as `level_type` aliases for `pressure`, `surface`, and `model_level` in keyword arguments and query mappings. `source.sel(parameter="t", level_type="pl", level=850)` selects 850 hPa. Pass `level_unit="Pa"` for level values in Pa. Use the canonical names in Query objects and JSON or YAML Request documents. See [GRIB level conventions](../source/guide/grib/levels.md) for surface and model levels.

Use `source.sel(parameter="gsw").one()` to read the original CEMC surface net short-wave field. The names `glw`, `gsw` and `hfx` select reviewed CEMC surface encodings and return `cedarkit.glw.raw`, `cedarkit.gsw.raw` and `cedarkit.hfx.raw`, respectively. The readings preserve the decoded values and retain the encoded statistical interval in metadata. Their xarray output omits the standard `units` attribute because the same encoding carries flux or accumulated energy across products.

For reviewed individual ensemble fields (PDT 1 or 11), `member` is the encoded `perturbationNumber` and `member_role` comes from the encoded forecast type. Use either selector to narrow a named query to ensemble fields, for example `source.sel(parameter="t2m", member_role="control").all()`. Explicit product queries use their catalog's member numbering. [WMO code table 4.6](https://raw.githubusercontent.com/wmo-im/GRIB2/v37/GRIB2_CodeFlag_4_6_CodeTable_en.csv)

`source.sel(parameter="t2m").explain()` and `Field.report` record the registry and mapping IDs, content versions and SHA-256 digests. File queries report `unchecked` with `expected_set_unknown` when an independent expected domain is absent. An explicit standalone bundle can be selected through `context` with both `parameter_registry` and `mappings.grib2` references.

### wgrib2 and ecCodes short names

For GRIB file and local archive sources, `parameter=` resolves an exact CedarKit
name, alias or ID first, then a short name from the bundled wgrib2 NCEP tables,
then the ecCodes `shortName` of each record. Use uppercase wgrib2 names and the
exact spelling of CedarKit and ecCodes names. The selected naming convention
applies even when other selectors leave no matching records. Use `cedarkit:`,
`wgrib2:` or `eccodes:` to select a particular convention. For example, bare
`APCP` uses the CedarKit accumulation definition. `wgrib2:APCP` selects records
that have the upstream short name.

```python
temperature = source.sel(
    parameter="TMP", level_type="pressure", level=850, level_unit="hPa"
).one()
height = source.sel(
    parameter="eccodes:gh", level_type="pressure", level=850, level_unit="hPa"
).one()
```

External short names use native GRIB selection and decoding. `explain()` shows
the effective native predicates. The field report records the upstream version
and digest when a query uses the wgrib2 table. For a name sent to ecCodes, an
absent match gives an empty `all()` result or a `no_match` error from `one()`.
Use the existing coordinate selectors to narrow short names that span multiple
levels or time windows.

## CEMC ORIG support in catalog v57

For named selection from full CEMC `grib2/orig` files, pass one of the
following dataset IDs to `from_source()`. Both an explicit file path
(`kind="file"`) and a mounted archive root (`kind="local"`) have been exercised
for all six products. Select the parameter by canonical name or stable CedarKit
ID. For archive queries, use the UTC initialization time, lead and file member
applicable to the record.

| Product | Dataset ID | Frozen originals read with v52 | Additional originals read with v57 |
| --- | --- | ---: | ---: |
| GFS | `cma_gfs_gmf` | 64 | 1 |
| MESO-1KM | `cma_meso_1km` | 43 | 1 |
| MESO-3KM | `cma_meso_3km` | 53 | 1 |
| TYM | `cma_tym` | 43 | 1 |
| GEPS | `cma_geps` | 320 | 0 |
| REPS | `cma_reps` | 227 | 1 (member 2) |

The v57 handoff reuses the v52 full-file results for 181,179 messages across
463 carrier groups. The five additional v57 originals are +6 h forecasts.
All 2,388 messages in those files passed named selection by both identifiers,
original-byte checks and xarray decoding. The 143 historical B05/B06 groups
(925 messages) have individual records for ORIG field selection and reading.

Acceptance checks the named binding and message position against the GRIB2
headers for the recorded cycles, leads, levels, encoded statistics and
members. Callers interpret the returned values for their applications.
A mapping with an applicable reviewed unit rule exposes standard
`units`. A raw-value branch preserves decoded values and missingness and
exposes the encoded metadata in `field.metadata["native_fields"]`. For
example, v57 reads MESO-3KM `cedarkit.ripbl` as decoded raw values. Its frozen
0, 6 and 48 h files from 2026-11-02 12 UTC carry the field at one-based
`count=29`.

For requests with no independent expected domain, available reads report
`unchecked` with `expected_set_unknown`.

The five additional cycle scans found zero exact matches for the seven B10
selectors. Those results cover the scanned cycles. Further cycles and product
versions require their own availability evidence. The CedarKit development
workspace's 1.5-06 handoff records the cycles, release artifacts and receipts.

The verified installation uses
`reki 2026.9.1.dev122+g1a95894.orig57` with `cedarkit-query 0.2.1`.
For rollback, install the pinned `reki 2026.9.1.dev121+g111cb2a.orig56`
artifact with its bundled catalog and product resources. If the caller pins
an explicit catalog path, switch it to the target `catalog-v1.json` with its
relative resources. The wheel's `reki/catalog/builtin/` directory contains the
full set. The parameter browser pairs schema 4 revision 17 with v57 and
revision 16 with v56. Switch the browser build and its `reviewed/` snapshot
together.

## Reviewed MESO-1KM column water

Catalog v41 adds the native `cma_meso_1km` binding for `cedarkit.pwat` from the
N04B-01 review. This batch is limited to 2026-11-02 12 UTC and leads 0, 6 and 48
hours, using the reviewed PDT 0, entire-atmosphere type 10 carrier and its
minute-encoded initial/forecast phases.

```python
from reki import from_source

with from_source({"kind": "local", "dataset": "cma_meso_1km", "root": "/CMADAAS"}) as source:
    field = source.sel(
        parameter="cedarkit.pwat",
        time="2026-11-02T12:00:00Z",
        step="PT6H",
    ).one()
    dataset = field.to_xarray()
```

`dataset.pwat` keeps the decoded values in `kg/m2`, with time, step, latitude
and longitude axes. The entire-atmosphere identity does not introduce a
numerical height coordinate. Source metadata retains the original
`kg m**-2`/`kg m-2` unit declarations; no humidity-unit or guessed scale conversion
is applied.

The frozen zero-hour original is an initialization constant zero. Its readable
value is not a claim that the physical atmosphere contains no column water.
These cells have no independent expected domain: available reads report
`unchecked` with `expected_set_unknown`, and `completeness="required"` does not
turn them into complete observations. Other cycles/leads and surface refinements
are outside this reviewed binding.

## Encoded value precision

For GRIB simple packing and lossless JPEG packing, field metadata exposes
`value_encoding` with the bit count, binary/decimal scales and half encoded
quantization step in the decoded value's unit. Constant fields have zero
quantization error. This evidence does not add native query keys, change decoded
values or assert a producer's physical uncertainty. The guarded precipitation
workflow can use it to retain small endpoint differences while rejecting larger
decreases; unsupported packing does not receive this precision declaration.
