"""E1: the fixed-data quick-start GRIB workflow."""

from __future__ import annotations

import json

from _helpers import open_ifs
from reki.operator import extract_region


source = open_ifs()
assert "2t" in source.unique("parameter")
field = source.sel(parameter="2t", level_type="heightAboveGround", level=2).first()
assert field is not None
data = field.to_xarray()
assert data.name == "2t"
assert data.shape == (241, 361)
subset = extract_region(data, 105, 125, 25, 45)
assert subset.shape == (81, 81)

print(json.dumps({"dims": list(data.dims), "subset_shape": list(subset.shape)}, sort_keys=True))
