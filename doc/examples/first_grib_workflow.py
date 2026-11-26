"""E1: the fixed-data quick-start GRIB workflow."""

from __future__ import annotations

import json

from _helpers import open_ifs
from reki.operator import extract_region


with open_ifs() as source:
    field = source.sel(parameter="t2m").one()
    assert field.metadata["native_fields"]["shortName"] == "2t"
    data = field.to_xarray()["t2m"].squeeze(drop=True)
assert data.name == "t2m"
assert data.shape == (241, 361)
subset = extract_region(data, 105, 125, 25, 45)
assert subset.shape == (81, 81)

print(json.dumps({"dims": list(data.dims), "subset_shape": list(subset.shape)}, sort_keys=True))
