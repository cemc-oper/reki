# Current-business CMA-GFS and CMA-MESO 3 km sources

The builtin catalog registers `cma_gfs_gmf` and `cma_meso_3km`, both with
`orig` / `current`, for bounded deterministic instantaneous subsets. `current`
selects the current business interpretation; it does not assert an official
producer release number or implement historical-version compatibility. The
catalog content version is 3, GFS mappings version 2, MESO mappings version 1,
and both parameter registries version 1. Their SHA pins remain exact. Reports
retain actual origins, message offsets and file fingerprints.

```python
from reki import from_source

source = from_source({"kind": "local", "dataset": "CMA-GFS", "root": "/CMADAAS"})
try:
    ds = source.sel(
        parameter="t", level_type="pressure", level=[925, 850, 500],
        time="2026-10-29T06:00:00Z", step=["PT24H", "PT48H", "PT72H"],
    ).all().to_xarray()
finally:
    source.close()

source = from_source({"kind": "local", "dataset": "CMA-MESO-3KM", "root": "/CMADAAS"})
try:
    ds = source.sel(
        parameter="t", level_type="pressure", level=850,
        time="2026-10-29T09:00:00Z", step="PT12H",
    ).one().to_xarray()
    soil = source.sel(
        parameter="st", layer={"top": .1, "bottom": .3},
        time="2026-10-29T09:00:00Z", step="PT12H",
    ).one().to_xarray()
finally:
    source.close()
```

These times are the latest origins frozen at the start of workspace I04 round-7.
Select an explicit origin appropriate to the next execution. Construction,
`sel` and `explain` never scan for a latest file. Discovery happens only at
`one` / `all`, using the registered UTC CMADAAS layouts. The root remains
explicit and deployment-owned. An explicit `file` source with the same dataset
uses the same business binding.

| Supported parameters / levels | GFS steps (hours) | MESO 3 km steps (hours) |
| --- | --- | --- |
| T/U/V/Q/RH at 1000, 925, 850, 700, 500 hPa | 0, 6, 12, 24, 48, 72 | 0, 3, 6, 12, 24, 36 |
| T2M, instantaneous U10M/V10M, PS/PSL | 0, 6, 12, 24, 48, 72 | 0, 3, 6, 12, 24, 36 |
| Soil temperature: GFS 0–.1, .1–.4, .4–1, 1–2 m; MESO 0–.1, .1–.3, .3–.6, .6–1 m | 0, 6, 12, 24, 48, 72 | 0, 3, 6, 12, 24, 36 |

MESO's first soil layer uses `cedarkit.st-0-10`. The other three use the existing
generic `cedarkit.st` identity with explicit layers. They receive distinct
variable names and retain all six flat boundary attributes. GFS-specific soil
variant names must not stand for MESO's different intervals. No parameter IDs
or definitions were added or reparented for this extension.

The directory also contains separate CN files with the same origin and lead.
Only exact ORIG paths establish this binding. Initial discovery that grouped
both products by lead was rejected by original-path checks; those failed draft
records are preserved separately in workspace evidence. The final inventory
keeps the full product identity and validates all six ORIG leads.

These are supported subsets of the existing orig products with
`complete_product_coverage=false`. There is no independently complete expected
domain, so `completeness="required"` cannot succeed merely because these
mappings or observations exist. Parameter lists and step lists must preserve
the supported pairs instead of widening them into a cross product.

Parameters and mappings are exported by cedarkit-param-db and packaged
verbatim. The builtin product selects exact references automatically. Anonymous
files retain no business defaults. External catalogs replace the builtin
catalog as a whole; they do not inherit its product or locator registrations.

Workspace I03 round-6 / I04 round-7 / I06 round-10 records original-file values,
multifile coordinate assembly, deterministic resource replay and clean-wheel
checks. Direct ecCodes comparisons establish decoder and query-chain
consistency. Independent physical and complete-product acceptance remain open.
