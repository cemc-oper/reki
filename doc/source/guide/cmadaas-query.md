# CMADaaS public queries

The default v34 catalog contains twelve live service bindings, retaining task 07B's sixteen mappings and adding 374 original-message-verified instantaneous mappings from task 07C. Install `reki[cmadaas]`, configure `~/.config/cedarkit.yaml` or `CEDARKIT_CONFIG`, and select the dataset directly:

```python
from reki import from_source

with from_source({"kind": "cmadaas", "dataset": "cma_gfs_gmf_cmadaas"}) as source:
    field = source.sel(
        parameter="cedarkit.t2m",
        time="2026-08-30T00:00:00Z",
        step="PT6H",
    ).one(completeness="required")
    dataset = field.to_xarray()
    report = field.report
```

The accepted samples cover each service's 2 m TEM field and the four GFS surface TEM, GPH, CPE and LPE cases. Twelve cases retain their task 07A interface and time. GFS and TYM analysis use the forecast-style interface with `validTime=0`, which is the actual supported binding for those dataCodes. REPS uses the verified 2026-11-04 06 UTC cycle instead of the unavailable historical 00 cycle. The independent expected domains contain the sixteen task 07B cells and 374 task 07C cells. Other permitted times retain `unchecked` completeness until their own expected domains are registered.

The source version `service-20261105` identifies the reviewed binding revision. It does not claim an official model release. UTC request association was checked against the matching original GRIB reference times and forecast hours. GFS returned 0.125° spacing despite its obsolete 0.25° product metadata. Actual response grids, source units and original fields are the evidence for these samples.

Returned names may be the requested element or the exact `element_levelType` identifier, such as `TEM_103`. Nonempty server `requestParams` are checked independently against all native business parameters and retained as a filtered `server_request_echo`. Copied client metadata remains request association evidence.

The reviewed `cmadaas.grid-array2d.reps.member` contract preserves REPS responses whose unit, element name and server request echo are empty. Its source unit comes from the pinned, original-field-verified mapping and is labelled `source_unit_basis="mapping"`; empty response headers remain empty in field metadata. A contradictory nonempty header still fails. REPS may include a neighboring grid point within one grid cell of the fixed rectangle; coordinates and values are retained. GEPS and REPS control services accept member 0; their perturbation domains were checked with scalar requests for all members 1–30 and 1–14, plus rejected boundary members.

Use the client candidate bundled with the task 07B acceptance artifacts. It corrects accumulated float32 header-step rounding within the declared endpoint precision bound, preserving explicit coordinate axes, field values and raw header fields. The source's owned MUSIC client uses summary logging. Injected clients retain their caller's configuration and ownership.

## Additional instantaneous fields

The public service parameter and mapping resources are version 2. The 64 parameter definitions and 390 mappings cover reviewed pressure levels, surface and 10 m fields, mean sea level, entire-atmosphere columns, cloud layers and diagnostic instantaneous fields. A unique reviewed mapping can supply its fixed vertical identity; an underspecified generic parameter with multiple applicable vertical mappings remains ambiguous. Pressure queries accept equivalent Pa and hPa declarations.

```python
with from_source({"kind": "cmadaas", "dataset": "cma_gfs_gmf_cmadaas"}) as source:
    temperature = source.sel(
        parameter="cedarkit.t",
        level_type="pressure",
        level=850,
        level_unit="hPa",
        time="2026-11-02T12:00:00Z",
        step="PT6H",
    ).one(completeness="required").to_xarray()
```

Non-REPS interface contract version 2 allows an empty response unit to use the pinned mapping only when the independent server parameter echo is present and verified. The mapping's unit was checked against the matching original carrier and the reviewed native product definition. Metadata preserves the empty `response_unit` and labels `source_unit_basis="mapping"`. Version 1 still requires response units outside the explicit REPS contract. Any contradictory nonempty unit or request echo fails.

Published level and lead-time domains follow the reviewed per-product historical inventory; the finite expected domains cover only the independently verified cells. Other supported levels, times and members retain `unchecked` completeness. Most mappings retain the fixed 39–41°N, 115–117°E rectangle. The GEPS perturbation pressure TEM mapping explicitly uses the full-grid interface: its accepted 2026-08-30 00 UTC, +6 h, member 1 field is the original 720 × 1440 grid. No implicit cropping or regridding is performed; combining incompatible grids retains the usual structured error.

The remaining 623 historical rows are explicitly assigned to follow-up tasks: service availability (07D), precipitation and accumulation identities (07E), time statistics and fluxes (07F), soil and cloud vertical identities (07G), and other diagnostics, units and aliases (07H). PRE and suffixed accumulation codes retain their own review obligations. A service error never becomes an empty accepted field or an expanded coverage claim.

## Task 07A offline candidate

Task 07A provides an independently replayable offline candidate for twelve historical CEMC service registrations. Select this dedicated candidate catalog explicitly to reproduce its original controlled contracts. The current default catalog uses the separately verified task 07B and 07C bindings described above.

```python
from reki import from_source

context = {"catalog": {"builtin": "reki.catalog.cmadaas.task07a"}}
with from_source(
    {"kind": "cmadaas", "dataset": "cma_gfs_gmf_cmadaas"},
    context=context,
    client=controlled_client,
) as source:
    selection = source.sel(
        parameter="cedarkit.t2m",
        time="2026-08-30T00:00:00Z",
        step="PT6H",
    )
    explanation = selection.explain()
    field = selection.one(completeness="required")
    dataset = field.to_xarray()
    report = field.report
```

`controlled_client` implements `callAPI_to_gridArray2D`, returning the MUSIC client's `GridArray2D` response with its request association metadata. The task's verification suite supplies this client without network access. Omitting `client` creates the configured MUSIC client when execution starts. Planning performs no client creation or service I/O. The source closes a client it creates when that client exposes `close`; an injected client remains owned by its caller.

The candidate catalog binds GFS, MESO-1KM, MESO-3KM and TYM analysis and forecast services, plus GEPS and REPS control and perturbation services. Analysis requests require a zero lead and omit `validTime`. Forecast requests use whole hours. Ensemble requests preserve `fcstMember=0` for control fields. The vertical translation table selects the native level-type and level pair together. This initial mapping set fixes the geographic rectangle to 39–41°N, 115–117°E.

All twelve services have a temperature mapping for the historical `TEM`, level type 103, level 2 row. GFS forecast also has the frozen surface `TEM`, `GPH`, `CPE` and `LPE` cases at 2026-08-30 00 UTC, +24 hours. The rain mappings have distinct parameter identities and the complete initialization-to-24-hour interval. Their reviewed water-equivalent conversion preserves numeric values from `kg/m2` to `mm`. PRE and suffixed accumulation codes remain outside the mapping set until their product definitions are verified.

The catalog's product version `candidate-07a` and UTC service clock describe the controlled fixture. Real service versions and time zones are unknown. Member ranges and request codes follow the historical inventory and require online confirmation. Task 07B must verify these properties, authorization and actual returned values before promoting a service binding into the default catalog.

Python, JSON and YAML use the same source, context and Query contract:

```json
{
  "api_version": "cedarkit.request/v1",
  "source": {"kind": "cmadaas", "dataset": "cma_gfs_gmf_cmadaas"},
  "context": {"catalog": {"builtin": "reki.catalog.cmadaas.task07a"}},
  "queries": [{
    "parameter": "cedarkit.t2m",
    "time": "2026-08-30T00:00:00Z",
    "step": "PT6H"
  }],
  "completeness": "required"
}
```

Only the finite independent fixture cells have verified expected domains. Other permitted selectors retain `unchecked` completeness; `required` cannot infer a product-wide domain from successful requests. Reports preserve resource pins, candidate interface parameters, request association checks and checked response units and grids. MUSIC copies time, lead, vertical and member metadata from the request. Reports label this evidence `request_association`. Actual server provenance requires separate online evidence.

Execution validates the returned element, unit, grid dimensions and coordinates before assembly. Empty grids produce no field, while a grid containing only missing values remains a field. Truncated payloads, service errors, authentication failures and timeouts retain separate structured errors. Duplicate branches share one scalar request during an execution. Repeated terminal operations reacquire responses.
