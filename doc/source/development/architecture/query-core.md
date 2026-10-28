# Stage 1.1 Query core (I05)

I05 introduces the shared Query path for **source declarations**, using the exact
`cedarkit_query.Query`, `Request`, errors, reports and explanations re-exported
from `reki`. This is a controlled core implementation, not evidence that any CEMC
product, business version, GRIB rule or CMADaaS interface is supported. I06 native
adapters have not been started or registered in this delivery. I05 remains in
progress until the relevant real backend slices have been integrated and verified.

The existing string/SourceSpec source route is temporarily retained for I08
consumers. It does not consume the new Query. The legacy CLI, query adapters and
old schemas used by those callers are not migrated by this change. A complete
stage 1.1 deployment cannot be made from this intermediate checkout.

## Public construction and inspection

This example can run without GRIB decoding, service credentials or a backend. Use
an actual existing input directory; construction checks its kind but does not
list its business files. The condition is a native selector, not a registered
business parameter or a claim about the directory's contents.

```python
from reki import Request, from_source

request = Request.from_dict({
    "api_version": "cedarkit.request/v1",
    "source": {"kind": "file", "directory": ".", "glob": "*.grib2"},
    "queries": [{"native": {"grib": {"discipline": 0}}}],
})
with from_source(request.source, context=request.context) as source:
    selected = source.sel(request.queries)
    explanation = selected.explain()
    assert explanation.analysis["translations"][0]["coverage"]["status"] == "pending"
```

Until I06 supplies a backend, executing `selected.all()` raises the shared
`QueryError(unsupported)` with `reason=translation_unavailable`; it never returns
a successful empty business result. Dataset sources additionally need exact I04
product/source facts; this core does not pick a version from filenames, dates or
catalog order. The internal integration entry below accepts those resolved facts.

For an integrated source, the public execution shape is:

```python
options = {} if request.completeness is None else {"completeness": request.completeness}
# Within the source's lifetime, after a real adapter is registered:
# fields = selected.all(**options)       # selection now executes
# ds = fields.to_xarray(rename=None)     # values now load; returns xr.Dataset
# report = fields.report                # presence facts; not value quality
```

`sel(Query(...))`, `sel([Query(...), ...])` and keyword `sel(...)` use the same
model. One call unions its branches; chained calls intersect them, preserving
input origins. Legal disjoint conditions form an empty selection. Every later
input is still validated against the immutable scope and definitions. Expansion
uses the shared effective discrete combination limit, never a returned-field,
file, network-request or grid-point count. A continuous interval has an unknown
static expansion count. No result, metadata, value or Dataset cache is added.

## Internal I05/I06 integration contract

`reki.selection.core.construct_source(configuration, backend)` takes an immutable
I04 `SourceConfiguration` and an internal backend. This is not a second public
Query schema or a backend injection option in Request. Production registration,
native rules, interface contracts and business evidence belong to I06/I03/I04.

| Operation/value | Obligation |
| --- | --- |
| `backend.plan(queries, configuration) -> Plan` | Pure; no discovery, scan, connection or value I/O, including when called by `sel`/`explain`. One ordered translation item per effective Query, with locally contiguous paired branches and real basis references. Coverage is `passed` only with proof; otherwise `pending`. |
| `Plan.expected` | One complete, independent finite identity set per Query, or `None`. Concrete normalized identities must satisfy the Query. Product applicability, legal combinations and completeness of this set need evidence; never reconstruct it from returned records. Unknown and empty have different meanings. |
| `backend.start(plan) -> Scan` | Terminal-only acquisition. `Scan.plan` may refine pending facts before yielding references; coverage must then be proven. `Scan.context` can add only source `paths`, `fingerprints`, `version`, not overwrite resource definitions/scope/defaults or expose config/client/authentication. |
| `Scan` iteration | Stable global source order, independent of Query/branch/concurrency order. Normal exhaustion certifies successful complete acquisition and required pagination. Truncation, target interpretation failure and service failure raise `SourceError`, never normal exhaustion. `Scan.close()` releases execution resources but leaves returned references valid for delayed loading. |
| `FieldReference` | Concrete shared Query identity; reliable `record_id` tied to source generation and record position; canonical metadata, sufficient grid definition, lazy spatial `DataArray` loader, and snapshot-local `(query_index, branch_index)` links. Equal business identity or equal values alone do not establish equal records. |
| Metadata | `parameter_id`, `parameter_name`, business `unit` and effective `fixed_conditions` must match the loaded registry. `source_unit` needs independent source evidence. Optional description, standard_name and statistics must be factual. Numeric vertical coordinates additionally require an explicit compatible `vertical_definition`. Affine conversion requires `quantity_kind=absolute_temperature`; temperature differences must not use an absolute-temperature offset. These are adapter facts, not new resource-schema fields. |
| `backend.close()` | Close owned resources once; never close an injected external client. QuerySource owns the backend lifetime and all associated fields/selections. |

The core checks **both residual and complete effective Query**, including native
keys, after interpretation. A broad candidate is not itself a match. Rule,
native metadata and decoder error classification remain the adapter's duty;
arbitrary programming errors are not converted into missing fields. Branch scope
and basis must reflect actual I04 applicability and the exact resources in the
report; no business product/version is manufactured here.

The terminal-only `selection.files.discover_paths` helper preserves literal file
list order, sorts normalized directory matches, and keeps registered local
template priority with lexical paths within each template. It renders only the
finite approved template fields and rejects path escape and unrepresentable
hourly times/steps. Missing predicted local files stay distinguishable from
configuration failure. `FileSnapshot.capture/verify/load` pins device/inode/size/
mtime/ctime before and after loading; a native adapter must use such a guard
around scanning/loading and include message position in record identity.
This stat fingerprint detects generation changes, not cryptographic content
equality; adapters must provide stronger source versions when their environment
requires them. None of these helpers scans GRIB or activates a real layout.

## Output, reports and lifetime

`first()` uses stable source order and may stop early under `available`; zero
match returns `None`. `one()` counts distinct actual records and fails as soon
as a second is found under `available`. Under `required`, each terminal first
exhausts the required range and checks original-query completeness; missing or
undetermined completeness precedes cardinality. `all()` retains different records
with duplicate business positions or incompatible grids for inspection.

`to_xarray` loads values and converts declared compatible units. Actual fields
alone form variables and coordinate domains; rectangular internal holes become
NaN. Completely absent variables/coordinate values are not invented. Actual
all-NaN records still count as existing. Applicable singleton axes remain, with
independent time/step, auxiliary valid_time/member_role, canonical vertical units
and ordering, retained horizontal direction/projection, layer variables and six
flat boundary attributes. Metadata conflicts, duplicate positions, ambiguous
names and incompatible grids fail instead of silently overwriting/interpolating.
Exact business variant names precede canonical layer names. Rename only changes
display names, preserving canonical IDs, names and boundary attributes.

Fields and collections expose immutable `QueryReport`. It separates candidate
coverage, acquisition execution and business presence, and makes no value quality
or conversion claim before loading. Dataset/data variables carry its independent
JSON snapshot in `cedarkit_query_report`. Completeness errors serialize a report
object; ordinary QueryError/SourceError omit it. Closing a source is idempotent;
old metadata/reports remain readable, but associated selection execution and
field/collection conversion fail. Already returned memory Datasets remain usable.

`tests/selection/` uses explicitly SYNTHETIC independent expected sets, paired
candidate plans, lazy values and disposable files. Passing it proves this core
mechanism, not Q17 product coverage or Q20 business acceptance. Real rules,
snapshot/pagination/stable-order evidence, units and backend integration must be
delivered by I06 and then verified with I05; cross-entry migration belongs to I08,
business acceptance to I09 and package combinations to I10.
