"""E1: deterministic core-GRIB summary used by future tutorial pages."""

from __future__ import annotations

import json

from _helpers import open_ifs


with open_ifs() as source:
    field = source.sel(native={"grib": {"shortName": "2t"}}, level_type="height_above_ground", level=2).one()
    data = field.to_xarray(rename="2t")["2t"].squeeze(drop=True)
assert tuple(data.dims) == ("latitude", "longitude")
assert tuple(data.shape) == (241, 361)

print(json.dumps({"dims": list(data.dims), "shape": list(data.shape)}, sort_keys=True))
