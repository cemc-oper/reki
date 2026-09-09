"""E1: region, sample, point, and grid processing from a GRIB field."""

from __future__ import annotations

import json

from _helpers import open_ifs
from reki.operator import extract_point, extract_region, interpolate_grid, sample_nearest


field = open_ifs().sel(parameter="2t", level_type="heightAboveGround", level=2).first()
assert field is not None
data = field.to_xarray()
subset = extract_region(data, 105, 125, 25, 45)
assert subset.shape == (81, 81)
coarse = sample_nearest(subset, longitude_step=2, latitude_step=2)
assert coarse.shape == (11, 11)
point = extract_point(data, latitude=39.9, longitude=116.4, scheme="nearest")
assert point.ndim == 0
target = subset.isel(latitude=slice(None, None, 8), longitude=slice(None, None, 8))
regridded = interpolate_grid(data, target)
assert regridded.shape == (11, 11)

print(json.dumps({"coarse_shape": list(coarse.shape), "grid_shape": list(regridded.shape), "subset_shape": list(subset.shape)}, sort_keys=True))
