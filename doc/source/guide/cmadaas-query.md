# CMADaaS public query candidates

Task 07A provides scalar grid execution for twelve historical CEMC service registrations. Install the `cmadaas` extra and select the dedicated candidate catalog explicitly. The default catalog keeps the existing local GRIB bindings and leaves its unverified service declarations pending.

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
