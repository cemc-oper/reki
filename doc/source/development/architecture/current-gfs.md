# Current-business CEMC sources

The builtin catalog registers `cma_gfs_gmf`, `cma_meso_3km`, `cma_meso_1km`, `cma_tym`,
`cma_geps` and `cma_reps`, all with `orig` / `current`, for bounded instantaneous
subsets, including individual ensemble members for GEPS/REPS. `current`
selects the current business interpretation; it does not assert an official
producer release number or implement historical-version compatibility. The
catalog content version is 10. GFS mappings use version 5; all other current
mappings use version 3. The GFS parameter registry uses version 3; the other five
use version 2. Their SHA pins remain exact. Reports
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


## GEPS/REPS member precipitation accumulations

The existing current products also expose original individual-member total
precipitation (`rain`, alias `APCP`) and convective precipitation (`rainc`,
alias `ACPCP`) at 0/6/24 hours. GEPS additionally exposes large-scale
precipitation (`rainnc`, alias `NCPCP`). These are PDT-11 accumulations since
initialization, not formal ensemble statistics or derived differences.

```python
with from_source({"kind": "local", "dataset": "CMA-REPS", "root": "/CMADAAS"}) as source:
    ds = source.sel(
        parameter="rain", time="2026-10-29T18:00:00Z",
        step=["PT6H", "PT24H"], member=[0, 1, 2, 14],
    ).all().to_xarray()
```

Three new definitions (`cedarkit.rain.since-initialization`,
`cedarkit.rainc.since-initialization`, and
`cedarkit.rainnc.since-initialization`) inherit the existing accumulation
identities and fix the period explicitly. The existing broader definitions
and stable IDs are preserved. Product-scoped names select the exact variants;
the broader IDs are not silently narrowed to this period.

The original start offset is zero, the encoded end is the result time, and
one range descriptor with accumulation/type-of-increment 1/2 has length
0/6/24 hours. The canonical step comes from the encoded end, rather than the
raw `forecastTime=0`. A zero-hour message remains a zero-length initial
accumulation, not an invented positive-duration trailing window. Field metadata
retains `statistics`, `statistical_interval`, and the original descriptor keys.
Multiple ranges, reanchored windows and conflicting end/length values are
not relabelled as this period.

Raw precipitation has units `kg/m2`; output uses the reviewed `mm` water-depth
identity. Their 1:1 numerical relationship is the specific water-equivalent
precipitation convention. Only the exact builtin product variants carry that
quantity evidence. It is not a global unit alias or a free mapping coefficient;
other mass/depth quantities and rates remain incompatible. Both source and
target units remain in metadata. When ecCodes `units` is `unknown`, this finite
path checks the standard `parameterUnits` and the declared mapping source unit;
conflicting declarations fail.

Workspace I03 round-9 / I04 round-10 / I06 round-13 retains the 169-row input,
adds 20 mappings to the combined version-2 GEPS/REPS bundles (52/40 rows),
and separately reviews the three new authored variants. The legacy migration
review remains 125 resolved / 96 needing evidence; six additional backend
coverage obligations for the new variants are recorded separately. Complete
provision, independent physical acceptance, snowfall conflicts and formal
ensemble statistics/probability/quantile products remain open.

## Current deterministic precipitation accumulations

The current GFS binding also provides total (`rain` / `APCP`), convective
(`rainc` / `ACPCP`) and large-scale (`rainnc` / `NCPCP`) precipitation at the
surface for 0, 6 and 24 hours. The current MESO 3 km binding provides total
precipitation at those same leads. MESO 3 km convective and large-scale
precipitation have no added mapping: the selected current messages and business
material do not establish those products. Existing instantaneous pairs remain.

```python
from reki import from_source

with from_source({"kind": "local", "dataset": "CMA-GFS", "root": "/CMADAAS"}) as source:
    rain = source.sel(
        parameter=["APCP", "ACPCP", "NCPCP"],
        time="2026-10-30T00:00:00Z",
        step=["PT6H", "PT24H"],
    ).all().to_xarray()
```

These PDT-8 fields reuse the reviewed `*.since-initialization` identities.
`forecastTime=0` is the interval start, while the coded interval end establishes
`step` and `valid_time`. A zero-hour field retains its zero-length accumulation;
it does not become instantaneous. A trailing window remains a different
identity, and no window is calculated by subtracting accumulations.

Native `kg/m2` and target `mm` remain separate. The reviewed water-equivalent
1:1 convention is activated only for these exact builtin identities. An ecCodes
`units=unknown` placeholder uses the verified `parameterUnits` and mapping
source-unit declaration; contradictory units fail. The DOCX GFS spelling `Mm`
is retained as source evidence, not registered as a global unit alias. Target
`mm` follows the original parameter declaration and reviewed definition.

The new finite rows separate initial analysis metadata from positive-lead
forecast metadata and reuse the existing time, statistics and unit rules.
Multiple intervals, unsupported increments, inconsistent endpoints, fixed-period
mismatches and unit conflicts keep their explicit diagnostics. These are
existing deterministic products with additional finite pairs; complete product
coverage, formal ensemble products and independent physical acceptance remain
separate obligations.


## Current MESO 1 km and TYM precipitation

MESO 1 km adds total precipitation (`APCP`, `rain`) at surface and 0, 6 and
12 hours. TYM adds total, convective and large-scale precipitation (`APCP`,
`ACPCP`, `NCPCP`) at surface and 0, 6 and 24 hours. All use the reviewed
since-initialization identities and the finite PDT-8 rules above. MESO 1 km
product scope includes 12 hours for precipitation; its existing instantaneous
pairs remain at 0, 6 and 24 hours. TYM's old instantaneous pairs are unchanged.

```python
with from_source({"kind": "local", "dataset": "CMA-MESO-1KM", "root": "/CMADAAS"}) as source:
    rain = source.sel(
        parameter="APCP", time="2026-10-30T09:00:00Z", step=["PT6H", "PT12H"],
    ).all().to_xarray()

with from_source({"kind": "local", "dataset": "CMA-TYM", "root": "/CMADAAS"}) as source:
    rain = source.sel(
        parameter=["APCP", "ACPCP", "NCPCP"],
        time="2026-10-30T06:00:00Z", step=["PT6H", "PT24H"],
    ).all().to_xarray()
```

These origins are the latest exact existing cycles frozen for workspace I04
round-13. The MESO 1 km cycle had no 24-hour file at discovery; no older cycle
was substituted. Raw MESO 1 km time units are minutes, while TYM uses hours.
The reference time, coded start, end and range length are checked in their
own units before normalization. Initial 0/0/0 processing/generating/reference
markers and forecast 1/2/1 markers remain distinct. A zero-length accumulation
retains its statistics even when the processing metadata identifies analysis.

The current MESO 1 km files checked contain total precipitation but no surface
convective or large-scale target messages. Historical model names do not
establish current product provision or interval semantics; those two bindings
remain evidence gaps. Native kg/m2, output mm, unknown-unit handling and unit
conflict diagnostics follow the same reviewed narrow convention. No products
are generated by subtracting accumulated fields, and these bindings do not
establish complete product coverage or formal ensemble statistics support.


## Common precipitation leads and cross-day pairs

The current finite precipitation pairs now include the following lead hours:

| System | Parameters | Supported accumulation leads (hours) |
| --- | --- | --- |
| GFS | Total, convective and large-scale | 0, 3, 6, 12, 24, 48, 72 |
| MESO 3 km | Total | 0, 1, 3, 6, 12, 24, 36 |
| MESO 1 km | Total | 0, 1, 3, 6, 12 |
| TYM | Total, convective and large-scale | 0, 3, 6, 12, 24, 48, 72 |
| GEPS | Total, convective and large-scale, members 0–30 | 0, 6, 12, 24, 48, 72 |
| REPS | Total and convective, members 0–14 | 0, 6, 12, 24, 48, 72 |

These additions use disjoint mapping rows; the original 205 rows remain
unchanged. That precipitation extension retained parameter resources at version 2
with identical bytes; the radiation addition below revises only the GFS registry.
Only the
reviewed precipitation provides entries receive additional leads; the existing
instantaneous and non-precipitation pairs retain their previous ranges. The
MESO 1 km product scope still includes 24 hours for old instantaneous pairs,
while its precipitation does not acquire that lead without current evidence.

Workspace I04 round-14 freezes GFS 06Z, MESO3 09Z, MESO1 12Z, TYM 06Z, GEPS 00Z
and REPS 06Z on 2026-10-30. The latest MESO1 cycle had no 24 h file at discovery;
its existing 12 h precipitation pair supplies a real cross-day check without
falling back to an older cycle. Each next execution must rediscover its latest
actual inputs rather than treating these example origins as live defaults.

```python
with from_source({"kind": "local", "dataset": "CMA-GFS", "root": "/CMADAAS"}) as source:
    rain = source.sel(
        parameter=["APCP", "ACPCP", "NCPCP"],
        time="2026-10-30T06:00:00Z", step=["PT12H", "PT48H", "PT72H"],
    ).all().to_xarray()

with from_source({"kind": "local", "dataset": "CMA-REPS", "root": "/CMADAAS"}) as source:
    control = source.sel(
        parameter="APCP", time="2026-10-30T06:00:00Z",
        valid_time="2026-11-02T06:00:00Z", member_role="control",
    ).one().to_xarray()
```

PDT8 deterministic and PDT11 individual-member accumulations keep their actual
reference, coded start, end, range length and raw time units. Crossing a UTC day
or month does not reset accumulation or change the origin directory. REPS
continues to locate files by the origin's Beijing date, independently of the
result valid date. Its raw ensemble-size 0 stays native evidence and does not
define a statistical population. Control member 0 and odd/even perturbation
kinds remain checked against the established numbering contract.

Native kg/m2 and output mm retain the reviewed narrow water-equivalent
convention; no duration multiplier or differencing is applied. Trailing windows,
formal ensemble statistics, probability and quantile products are not generated.
The finite entries do not establish full product coverage; unknown complete
domains continue to reject required-completeness claims.
For builtin current products, an omitted step uses the selected parameter's
single declared lead domain intersected with the configuration bounds. Expanding
precipitation leads therefore preserves old temperature and pressure calls that
omit step. Explicit steps and steps inferred from time plus valid_time retain
strict compatibility checks; external catalogs do not inherit this builtin policy. Product provides declarations
are interpreted against intrinsic product bounds; a caller's narrower context
bounds constrain its queries rather than requiring every provided product entry
to fit the caller's scope. Direct ecCodes numeric
comparisons are same-decoder consistency checks, not independent physical
acceptance.

## Finite directional clear-sky radiation energy

GFS now supplies `guswc-since-initialization` and
`gdlwc-since-initialization` at surface, at leads 0 and 6 hours. These are
time-integrated upward short-wave and downward long-wave radiation under clear
sky, in `J/m2`. Original `paraNum.h` cases 107/106 declare watt-seconds per area;
the business table and original PDT8 messages corroborate this energy quantity.
The single coded accumulation starts at the forecast reference and ends at the
message's explicit interval endpoint. The reference, endpoint and coded duration
are all checked by the existing time/statistics rules.

```python
with from_source({"kind": "local", "dataset": "CMA-GFS", "root": "/CMADAAS"}) as source:
    energy = source.sel(
        parameter=["guswc-since-initialization", "gdlwc-since-initialization"],
        time="2026-10-30T12:00:00Z", step=["PT0H", "PT6H"],
    ).all().to_xarray()
```

This example freezes a cycle at least 24 hours old. New validation batches
prefer eligible 12UTC cycles and REPS06UTC, and check file fingerprints before
and after reading. Cycle selection here is an evidence policy; it does not add
an automatic rolling-cycle default to the API.

Values retain their native signs and magnitudes. The checked GFS upward
component contains negative values; its directional name does not assert that
positive means upward. No sign reversal, duration scaling, mean-flux conversion,
or accumulated-field subtraction is performed. `W/m2` and `J/m2` remain distinct;
the shared unit aliases only normalize their observed SI spellings.

The other five systems acquire no radiation bindings from this addition.
HFX's actual `2/0/24` messages combine a flux unit with an accumulation code;
the producer's physical processing and sign convention remain required evidence.
Non-clear upward radiation has a similar unit conflict. Restoring the TUSWC
authoring definition fixes its inherited energy unit and does not register a
top-of-atmosphere product. Full provision domains and independent physical
acceptance remain open; direct ecCodes comparisons are decoder consistency
checks. Formal ensemble statistics, probability and quantiles remain outside
this finite binding.
