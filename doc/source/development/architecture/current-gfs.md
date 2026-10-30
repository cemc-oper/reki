# Current-business CEMC sources

The builtin catalog registers `cma_gfs_gmf`, `cma_meso_3km`, `cma_meso_1km`, `cma_tym`,
`cma_geps` and `cma_reps`, all with `orig` / `current`, for bounded instantaneous
subsets, including individual ensemble members for GEPS/REPS. `current`
selects the current business interpretation; it does not assert an official
producer release number or implement historical-version compatibility. The
catalog content version is 5, GFS mappings version 2, all other current mappings
version 1, and all parameter registries version 1. Their SHA pins remain exact. Reports
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
Complete product domains and independent physical
acceptance remain open for all current registrations.

## Current GEPS/REPS original members

`CMA-GEPS` supports members 0–30, T/U/V/Q/RH at 850/500 hPa, T2M,
U10M/V10M and PS/PSL. `CMA-REPS` supports members 0–14, T/U/V/RH at
850/500 hPa, T2M, U10M/V10M and PSL. Both bindings support hours 0, 6 and
24 only. REPS Q and PS have no suitable instantaneous candidates in the
selected files and remain unregistered; this does not establish permanent
absence. Formal ensemble statistics, probabilities and quantiles are separate
products and are outside these member bindings.

```python
with from_source({"kind": "local", "dataset": "CMA-GEPS", "root": "/CMADAAS"}) as source:
    members = source.sel(
        parameter="t", level_type="pressure", level=[850, 500],
        time="2026-10-29T12:00:00Z", step=["PT6H", "PT24H"], member=[0, 1, 2, 30],
    ).all().to_xarray()

with from_source({"kind": "local", "dataset": "CMA-REPS", "root": "/CMADAAS"}) as source:
    control = source.sel(
        parameter="t2m", time="2026-10-29T18:00:00Z", step="PT6H", member_role="control",
    ).one().to_xarray()
    all_members = source.sel(
        parameter="t2m", time="2026-10-29T18:00:00Z", step="PT6H",
    ).all().to_xarray()
```

Member selection uses a reviewed joint table of native ensemble kind and
perturbation number. Member 0 is the control (kind 0); positive odd members
use kind 3, and positive even members kind 2. The public role is perturbation
for both signs; wrong kind/number combinations are not silently renumbered.
Role-only selection narrows the finite default member domain, while an
explicit contradictory number/role selection still fails. Dataset roles may
be overridden through the existing context contract, but an override that
contradicts native member attributes fails.

These instantaneous member messages use PDT 1, generating-process type 4 and
processed-data type 3/4 for control/perturbation. The reference-time flag is
0 at hour 0 and 1 at hours 6/24; a zero-hour member field keeps its member
identity. Native ensemble-size values are 31 for GEPS and 0 for REPS. REPS's
zero is preserved as raw metadata and cannot establish a member population.

GEPS directory dates and filename times are UTC. REPS directory dates use
the Beijing date of the UTC reference time: the 2026-10-29 18Z cycle is in
`ORIG-DATA/NAFP/CMA-REPS/2026/20261030/`, while its filename still contains
`20261029180000`. This locator rule changes no canonical time or step. The
old data-finder REPS YAML remains historical input; the current binding uses
its own verified dataset identity and directory rule.

Workspace I03 round-8 / I04 round-9 / I06 round-12 freezes GEPS 2026102912Z
and REPS 2026102918Z, a 138-file member-header census and 362 distinct
instantaneous messages in 62 files. The old DOCX statement REPS 00–15 is
retained. The current finite binding uses the confirmed 0–14 target and
observed current member inventory, and registers no member 15; applicability
of the old statement remains an explicit historical evidence gap.

There is no independently complete expected domain. `required` completeness
continues to fail, and direct ecCodes comparison establishes same-decoder
consistency only. External catalogs do not inherit these numbering tables.
