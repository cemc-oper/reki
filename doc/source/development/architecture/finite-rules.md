# Finite rules and backend slices (I06)

The fourth slice adds internal `translation.header_evidence` for explicitly
referenced files: encoded-byte SHA-256, generation fingerprints, selected scalar
headers and raw section 4 descriptors for templates 8/11. It never requests
business value or coordinate arrays. Missing, undefined, multiple and getter-error
states remain separate from a real zero. Repeated descriptors retain encoded
order; no ranked ecCodes key syntax is used. File generations are verified around
hashing and collection. The workspace evidence index records the 16 manifest
files and 199 selected headers; this is neither a full message inventory nor
new parameter/product coverage. Existing header facts, portal UI pagination,
synthetic empty-grid examples and historical tests do not establish service
absence, complete acquisition or product snapshot semantics. The bounded
transport therefore retains its explicit empty-grid error and pending complete
retrieval check. Legacy inventory output remains historical; its current
`centre:int` fallback issue is recorded separately from this typed collector.

I06 is **in progress**. This implementation provides finite rule functions, an
explicit-file ecCodes backend, and an internal controlled single-grid service
transport. Its tests use synthetic definitions, generated GRIB messages, a
fake service and the actual nuwe client with injected offline HTTP/protobuf responses. They prove mechanisms, not CEMC product provision, real service
availability, Q17 coverage or Q20 acceptance. No production CMADaaS interface
contract, parameter mapping or product binding is registered by this change.

## Entry and ownership boundaries

A Mapping passed to `reki.from_source` uses the shared Request source contract.
An explicit `file` source selects the finite GRIB backend; construction and
`sel`/`explain` perform no file discovery, decoding or service calls. Acquisition
starts at `first`/`one`/`all`; values load at `to_xarray`. A regular bare GRIB2
stream in the supported profile can be inspected with a native selector without
inventing a parameter identity. Business queries require exact applicable
parameter/mapping definitions and product context where those definitions demand
it. Parameter names, filename dates and template row counts do not supply that
context. Dataset/local/service selection still needs explicit I04 resolved
product/source facts; public Request has no new product/version override.

Internally, `construct_source(configuration, backend)` uses the I05 interface.
The controlled `CmadaasBackend` requires an exact `InterfaceContract` reference,
a joint layer table, complete fixed statistics and an explicit transport. Its
wrapper shape is deliberately not a claim that a raw MUSIC/nuwe response already
has these properties. `NuweGridTransport(client, contract)` now connects the actual
`callAPI_to_gridArray2D` boundary using an explicitly supplied client. It preserves
the raw response and an immutable invocation instead of reconstructing association
from DataArray attrs. Proving each real interface and registering production
contracts remain I06 work. Owned transports close once;
external transports stay open. Existing string/SourceSpec callers remain on the
legacy route pending I08.

## Rule applicability

The GRIB slice explicitly registers **edition 2, master table 4, local table 0**.
Other master/local versions and GRIB1 canonical interpretation remain unsupported
until separately implemented and verified. Built-in ecCodes samples in this
round have this profile; their table version is not a CEMC business version.
All candidate interpretation checks the raw centre/subcentre/table/template
context. Local table zero with a local-use parameter/category/discipline code is
a known metadata inconsistency; a nonzero unregistered local table remains an
unsupported encoding, not damaged data. No local-1 interpretation was inferred
from old parameter names. Unsupported native forms fail as such instead of appearing as missing
business fields or damaged messages.

| Rule | Implemented finite path | Explicit boundary / required input |
| --- | --- | --- |
| `grib.fixed_surfaces` | Named surface/top/entire atmosphere/MSL; pressure, altitude, height above ground and depth; scaled equivalent encodings; same-kind numeric layers with physical boundary ordering | Model level needs an explicit vertical definition; mixed/named layer bounds and other fixed-surface meanings need additional paths. Missing second surface means a single surface, not a fabricated layer. |
| `grib.time` | Templates 0/1, 8/11, 2/12, 6/10, 5/9; UTC reference significance 0/1; fixed seconds/minutes/hours/days and 3/6/12 hours; interval end becomes step | Statistical windows: one range, increment type 2, explicitly encoded end consistent with start and length. Calendar units, negative forecast offsets, other reference meanings, multiple ranges and leap seconds are unsupported. |
| `grib.member` | Templates 1/11; native type and perturbation number interpreted jointly; known native control/perturbation types; optional configured role consistency | An independently justified numbering map is mandatory for canonical members. No implicit 0/control identity or offset. Aggregate ensemble products do not acquire a member axis. |
| `grib.statistics` | Native instantaneous templates 0/1; fixed time mean/accumulation/min/max with exact period; ensemble unweighted mean/min/max; percentile; probability below/above limits and between lower-inclusive/upper-exclusive bounds | Ensemble object, population, method and event definitions must be explicit. Distinct trailing/since-init identities remain distinct. Probability limits can be signed and use object units separately from field probability units. Weighted/other derived forms and equality/category events are unsupported. |
| `cmadaas.vertical_table` | Exact `(levelType, fcstLevel)` text pair; forward interpretation and inverse paired candidates; no numeric-text coercion; contradictory rows rejected | Explicit joint table and actual call association; table entries do not prove product provision or justify enumerating omitted axes. |
| `cmadaas.time_fields` | Exact 14-digit service timestamp, explicit service timezone, independent step; UTC normalization and hour precision | No implicit analysis PT0H. Missing fields need a declared finite contract; ambiguous DST is unsupported and nonexistent local time is invalid. |
| `cmadaas.member_field` | Explicit member table or a contract proving canonical numbering, checked against configured member role | No default member or numbering inference. |
| `cmadaas.statistics_fields` | Explicit fixed time statistics; exact interval period and role-derived provenance | No omitted-statistics-to-instantaneous default. Ensemble service statistics remain unsupported in this slice. |
| `common.value_unit` | Response unit and optional mapping source-unit agreement; compatible target units; exact scale/offset requirement; probability field versus object threshold units | Source unit cannot be inferred from target. Affine conversion requires explicit absolute-temperature meaning. Values are converted by the existing output layer only when loaded. |

Rule configuration remains owned and validated by `cedarkit_query.validate_rule`.
There is no arbitrary formula, field-mapping or private options escape hatch.
Omitting Query statistics imposes no statistical restriction; it never means
instantaneous by default. A fixed parameter definition may add its own explicit
statistics.

## Actual encoding verification in the second I06 slice

All ten templates (0/8, 1/11, 2/12, 5/9, 6/10) now have actual ecCodes encoding,
file scanning, fixed-statistic interpretation, independent expected identities,
selection/reporting and numerical Dataset output tests. Each also has actual
pressure-layer output and rejection of a different level. Interval templates
separately check interval-end selection and reject relabelling a trailing
accumulation as since-initialization. Equal raw member numbers with different
native types remain distinct under an explicit synthetic joint mapping.
These are bounded synthetic cases, not every valid form in a template or real
product evidence. Master/local and grid restrictions above remain unchanged.

Probability templates need two distinct unit facts. The native `parameterUnits`
field supplies the event-object threshold unit; its exact text is retained. The
finite spelling `m s-1` is normalized to `m/s`. The packed probability field's
percentage/fraction scale requires an explicit `common.value_unit.source_unit`
mapping declaration: the backend never infers it from the target unit. That
declaration must have actual encoding evidence before becoming a business
mapping. Tests independently encode signed wind thresholds and percent values,
then check dimensionless fractional output. No new rule configuration is added.

## Acquisition, output and diagnostics

The GRIB backend scans headers in stable file/message order, deduplicates physical
file aliases and retains source generation plus message offset as record identity.
It checks generation before and after delayed value loading. The new shared
`reki.grib_io` boundary owns ecCodes handles; old internal import paths forward to
it. The new path does not import cfgrib or the legacy reader package. Removing
legacy cfgrib callers and dependency is still joint I06/I08 work.

The current output decoder supports regular latitude/longitude grids with
row-consecutive, non-alternating scanning. It preserves horizontal direction,
uses the native bitmap for missing values and treats actual all-NaN fields as
present. The raw grid template, dimensions, point count, scanning flags and encoded
coordinate/increment fields are retained in native metadata without expanding the
accepted native Query selector keys. Positive dimensions, point count and coordinate
array lengths are checked before reshape; inconsistencies raise SourceError. Other grid/scanning paths are explicit implementation gaps. Generated
tests independently check values, metadata, delayed loading, stable order,
truncation, resource closure and source generation changes.

The original controlled wrapper verifies exact single-grid shape, integer record
count, absence of truncation, and correspondence to the immutable actual business
parameters. The actual nuwe adapter instead binds the exact raw `GridArray2D` to
its invocation and contract; it does not require a fabricated server echo. Native
`RequestInfo.row_count`/`col_count` are not treated as a number of returned fields. Response facts and verified request-association facts retain separate
provenance; fixed definitions retain a third source. A request is never copied
into an unidentified response. The exact response is attached internally to its
`CallRecord`; public reports omit response arrays, full requests and authentication.
The client copies some request values into metadata/attrs. These do not become
response-derived time/layer/member facts; the adapter drops those attrs from the
value array and rules retain `request_association` provenance. Errors are mapped
from actual client request status without exposing server payloads or signed URLs.
Empty grids have no proven field identity in this finite contract and fail
explicitly; a business absence interpretation needs its own supported evidence.
The underlying client/HTTP session remains caller-owned. Closing an owned adapter
only closes that adapter. No production interface, pagination or snapshot proof
is inferred from successful protobuf/grid decoding.

Only identical requests within one terminal execution share acquisition. There
is no result cache across executions. The returned service grid is materialized
and copied within acquisition, the allowed eager service boundary.

`Scan.checks` refines predeclared checks using actual acquisition facts. Reports
keep candidate coverage, execution exhaustion and independent expected-domain
presence separate. Unsupported translation is a Query error; missing context,
missing native metadata, inconsistent native metadata and unsupported native
encoding are distinct metadata reasons. Native stream/decode/transport failures
raise SourceError. None becomes normal EOF, an empty field or a partial success.
An independent complete expected domain may be supplied internally; it is never
reconstructed from observations, a table or observed returned fields.

## Field-level review and bounded wire requests in the third slice

The reviewed M03/M06 inventory retains parameter/profile identities and derived
vertical/time labels. It omits grid type/dimensions/scanning flags and most raw
surface/time fields. The workspace audit records these absences, legacy fallback
limitations and original sample references; no new raw business scan was performed.
Historical observations do not prove that a grid or product is unsupported, nor
supply a complete versioned business domain. Local-1 codes need their actual local
definitions; the master/local profile restrictions above remain unchanged.

`nuwe_wire.GRID_WIRE_PROFILES` now validates six explicitly reviewed native request
shapes: analysis by time/layer, forecast by time/layer/step, and forecast member
variants, each with or without rectangle endpoints. These are wire declarations,
not published product/interface business bindings. Broad time-only, multiple-level
and time-range interfaces need separate identity interpretation. Raw response-axis
bindings are rejected because RetGridArray2D has no native time/layer/member axes;
those facts require verified request association and product context.

The bounded adapter requires a scalar layer even where the portal makes analysis
fcstLevel optional. It validates complete role bindings, timestamp/calendar format,
single values and declared validTime hours before HTTP, including during pure
backend planning. It preserves native layer/member code text and does not infer
canonical meaning, numbering, timezone or business versions. Filters, thinning,
province selectors and fabricated pagination/snapshot options are outside this
finite shape. Rectangle shapes have low-level adapter tests; the current Query
backend does not emit rectangle endpoints, so their complete Query integration
remains a separate implementation task when justified by product/source facts.

The portal's file-info return label and client-return prose conflict; the current
adapter accepts only its actual GridArray2D/protobuf implementation. Snapshot
metadata time is not a business version. Portal limit labels (-1, zero, no-limit)
and RequestInfo row/column counters do not prove a complete business return. No
reviewed protobuf field establishes a product snapshot or revision; execution
timestamps are not substituted for one. Empty-grid semantics remain unresolved.

For the actual nuwe adapter, `complete_retrieval_supported` stays **pending** in
both explanation and execution reports. Successfully acquiring and decoding the
finite call set can establish request association and field presence while leaving
product-level retrieval/snapshot evidence unverified. Owned/external lifecycle is
unchanged. A nonempty all-NaN grid is an actual field; structurally short grids
fail decoding. Neither is silently reclassified as normal absence. The original
explicit synthetic transport keeps its own declared controlled contract.

## Verification and continuation

`tests/translation` records the controlled rule and backend checks.
`tests/selection` and the selected catalog/source/reader regressions protect the
I05 integration. The workspace I06 evidence directory records exact commands,
source and installed-package results, source/artifact hashes and the G17/G20
responsibilities. Existing I05 evidence retains its original date and scope.

Further implementation can extend finite master/local profiles, grids, time
ranges, GRIB1 and other legal statistics using sufficiently precise definitions
and controlled samples. Real numbering, units/quantity meanings, product
populations, versioned provision, MUSIC associations/completeness and service
snapshots need concrete business/protocol evidence as well. I06 must distinguish
these implementation tasks from I03/I04 definition work and I09 acceptance;
passing this synthetic suite closes none of their original evidence gaps.
