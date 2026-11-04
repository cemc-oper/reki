# Native field queries

Open a GRIB file with `reki.from_source({"kind": "file", "path": path})`. Pass `native={"grib": {...}}` to `sel` using the encoded scalar keys of the intended record. For CEMC local tables, include centre, table version, parameter triple, PDT or fixed surface keys as needed. Use `Field.metadata["native_fields"]` to inspect the selected record.

`first()` returns the first match, `one()` requires one match and `all()` returns all matching fields. `to_xarray(rename="original")` gives a readable variable name for a single native field. Returned values follow the original scan order. Missing points follow GRIB packing and bitmap information. An unrecognized local parameter or fixed-surface code can still be selected by its encoded keys.

Local sources use dataset-specific file layouts. Supply the origin in UTC, and optionally the lead or file member. For multi-record queries, a successful scan is bounded by the selected files. Product-wide completeness requires its own independent domain.
