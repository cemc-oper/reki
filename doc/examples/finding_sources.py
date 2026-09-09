"""E1: file and memory sources used by the data-finding tutorial."""

from __future__ import annotations

import json

import numpy as np

from _helpers import frozen_ifs_path
from reki import from_source


reader = from_source("file", frozen_ifs_path())
field = reader.sel(parameter="2t", level_type="heightAboveGround", level=2).first()
assert field is not None
assert field.to_xarray().shape == (241, 361)
memory = from_source("memory", np.arange(4)).to_xarray()
assert memory.values.tolist() == [0, 1, 2, 3]

print(json.dumps({"file_shape": [241, 361], "memory": memory.values.tolist()}, sort_keys=True))
