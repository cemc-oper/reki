# Native field queries

Open a GRIB file with `reki.from_source({"kind": "file", "path": path})`. Pass `native={"grib": {...}}` to `sel` using the encoded scalar keys of the intended record. For CEMC local tables, include centre, table version, parameter triple, PDT or fixed surface keys as needed. Use `Field.metadata["native_fields"]` to inspect the selected record.

`first()` returns the first match, `one()` requires one match and `all()` returns all matching fields. `to_xarray(rename="original")` gives a readable variable name for a single native field. Returned values follow the original scan order. Missing points follow GRIB packing and bitmap information. An unrecognized local parameter or fixed-surface code can still be selected by its encoded keys.

Local sources use dataset-specific file layouts. Supply the origin in UTC, and optionally the lead or file member. For multi-record queries, a successful scan is bounded by the selected files. Product-wide completeness requires its own independent domain.

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
