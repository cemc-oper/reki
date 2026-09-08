"""E1: deterministic core-GRIB summary used by future tutorial pages."""

from __future__ import annotations

import json

from _helpers import open_ifs, temporary_index


with temporary_index() as index_dir:
    field = open_ifs("core", index_policy="auto", index_dir=index_dir).sel(
        parameter="2t", level_type="heightAboveGround", level=2,
    ).first()
    assert field is not None
    data = field.to_xarray()
    assert tuple(data.dims) == ("latitude", "longitude")
    assert tuple(data.shape) == (241, 361)
    assert list(index_dir.glob("*.sqlite"))

print(json.dumps({"dims": list(data.dims), "shape": list(data.shape)}, sort_keys=True))
