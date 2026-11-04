# Native query execution

cedarkit-query validates native predicates and coordinates. reki resolves the dataset layout, scans GRIB headers, and retains source fingerprint and message offset. Matching references load values on demand. File generation is checked before and after the load. ecCodes supplies the grid, values and missingness. Assembly preserves scan order and checks grid compatibility.

Generic time and vertical coordinates are optional projections of encoded fields. If a projection is unavailable, the corresponding native scalar keys remain usable for selection.
