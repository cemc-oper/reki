# Query contract (stage 1)

`SourceSpec` is an immutable, serializable source description. `FieldQuery`
describes only a field requirement. New code uses `reader.sel(query).one()` for
required fields and `one_or_none()` for optional fields; `first()` remains the
compatible permissive API.

## Xarray contract matrix

Normalization is non-mutating. Validation inspects metadata only and defaults to
`warn`, so it does not compute lazy values or alter legacy reader return values.

| Item | Stage-1 rule | Status / exception |
| --- | --- | --- |
| Coordinates | Use `latitude`, `longitude`, `time`, `step`, `valid_time`, `level`, and `number`/`member` when supplied. | GRIB, NetCDF, GrADS and CMADaaS offline coverage. |
| Longitude | Preserve reader-native range and order. | No implicit `0..360` / `-180..180` conversion. Original range is therefore directly traceable. |
| Latitude | Preserve native one-dimensional direction. | Two-dimensional grids are preserved as a documented exception. |
| Time | Preserve xarray datetime dtype; readers retaining both values must satisfy `time + step = valid_time`. | No timezone conversion is performed. |
| Level | Use `level` where emitted; retain GRIB level type in source attributes. | Reader-specific names are not renamed in this phase. |
| Parameter | Use the decoded stable data name; preserve GRIB identifiers in attrs. | No parameter-registry migration. |
| Units | Store units in `attrs["units"]`. | Missing units emit `missing-units`; unknown units are retained verbatim. |
| Grid / CRS | Preserve grid mapping and coordinate topology. | Unknown CRS emits no fabricated CRS. |
| Statistics | Preserve `stepType`, time-range and accumulation attributes. | No inferred statistical meaning. |
| Ensemble | Preserve `number`/`member` and control-member representation. | No member normalization where a reader does not emit it. |
| Provenance | `normalize_data_array(..., source=...)` records `reki_source`. | Source summaries must be redacted before being supplied. |

The only normalized stage-1 metadata issue is `missing-units`. The following
documented backlog is intentionally warn-only: `XR-001` longitude/latitude
orientation, `XR-002` CRS/grid mapping, `XR-003` two-dimensional coordinates,
`XR-004` ensemble representation, and `XR-005` accumulated/statistical fields.
Each retains reader-native metadata rather than silently changing array layout or
numerical semantics; fixture expansion belongs to stage 2/3 review.
