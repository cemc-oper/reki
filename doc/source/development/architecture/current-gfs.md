# Current-business CMA-GFS and CMA-MESO 3 km sources

The builtin catalog registers `cma_gfs_gmf`, `cma_meso_3km`, `cma_meso_1km` and `cma_tym`, all with
`orig` / `current`, for bounded deterministic instantaneous subsets. `current`
selects the current business interpretation; it does not assert an official
producer release number or implement historical-version compatibility. The
catalog content version is 4, GFS mappings version 2, MESO mappings version 1,
the new MESO1 and TYM mappings version 1, and all parameter registries version 1. Their SHA pins remain exact. Reports
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


## Current MESO 1 km analysis/forecast and TYM

`CMA-MESO-1KM` and `CMA-TYM` now use their own exact current mapping and
parameter resources. Both expose the existing ORIG product at hours 0, 6 and
24. Zero-hour instantaneous messages must have processed-data/reference/
generating-process flags 0/0/0 (analysis); positive hours require 1/1/2
(forecast). These are separate native mapping rows, selected by explicit
`step`, within the same real ORIG product. No new public query syntax or
CMADaaS service binding is introduced.

Both support T/U/V/Q/RH at 850 and 500 hPa, T2M, U10M/V10M, and PS/PSL.
TYM additionally supports soil temperature at 0–.1, .1–.3, .3–.6 and .6–1 m;
the latter three use generic `st` with explicit layers. MESO1 soil fields
remain outside this finite binding because the selected current files supply
no reviewed instantaneous candidates. This does not prove permanent absence.

```python
source = from_source({"kind": "local", "dataset": "CMA-MESO-1KM", "root": "/CMADAAS"})
try:
    analysis = source.sel(parameter="t2m", time="2026-10-29T12:00:00Z", step="PT0H").one().to_xarray()
    forecast = source.sel(parameter="t", level_type="pressure", level=850,
                          time="2026-10-29T12:00:00Z", step="PT6H").one().to_xarray()
finally:
    source.close()
```

Workspace I03 round-7 / I04 round-8 / I06 round-11 records the frozen latest
MESO1 12Z and TYM 06Z original files, full-field checks and clean installation.
MESO1 fields contain 37,587,511 points each; public `all` returns lazy references,
so verification materializes complete individual fields to bound memory.
GEPS/REPS remain without registered current products and are deferred to the
next member-aware batch. Complete product domains and independent physical
acceptance remain open for all current registrations.
