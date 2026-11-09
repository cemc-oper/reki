"""E1: file and memory sources used by the data-finding tutorial."""

from __future__ import annotations

import json

import numpy as np
import xarray as xr

from _helpers import frozen_ifs_path
from reki import from_source


with from_source({"kind": "file", "path": str(frozen_ifs_path())}) as source:
    field = source.sel(native={"grib": {"shortName": "2t"}}, level_type="height_above_ground", level=2).one()
    assert field.to_xarray(rename="t2m").t2m.squeeze(drop=True).shape == (241, 361)
# In-memory arrays already belong to xarray; public meteorological source construction is unnecessary.
memory = xr.DataArray(np.arange(4))
assert memory.values.tolist() == [0, 1, 2, 3]

print(json.dumps({"file_shape": [241, 361], "memory": memory.values.tolist()}, sort_keys=True))
