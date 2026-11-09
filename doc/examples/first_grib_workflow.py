"""E1: the fixed-data quick-start GRIB workflow."""

from __future__ import annotations

import json

from _helpers import open_ifs
from reki.operator import extract_region


with open_ifs() as source:
    field = source.sel(native={"grib": {"shortName": "2t"}}, level_type="height_above_ground", level=2).one()
    data = field.to_xarray(rename="2t")["2t"].squeeze(drop=True)
assert data.name == "2t"
assert data.shape == (241, 361)
subset = extract_region(data, 105, 125, 25, 45)
assert subset.shape == (81, 81)

print(json.dumps({"dims": list(data.dims), "subset_shape": list(subset.shape)}, sort_keys=True))
