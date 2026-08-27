# Query contract (stage 1)

`SourceSpec` is an immutable, serializable source description.  `FieldQuery`
describes only a field requirement.  New code should use `reader.sel(query).one()`
for required fields and `one_or_none()` for optional fields; `first()` remains the
compatible, permissive API.

The initial xarray contract uses `latitude`, `longitude`, `time`, `step`,
`valid_time`, `level`, and `number`/`member` where supplied by a reader.  Source
parameter identifiers and level type remain in attributes.  Normalization is
non-mutating and validation defaults to warnings so legacy reader return values
are not changed.  Missing units currently produce the stable `missing-units`
issue; longitude range, latitude direction, CRS and two-dimensional grids remain
reader-specific documented exceptions pending the stage-2 review.
