"""Shared helpers for deterministic, standalone documentation examples."""

from __future__ import annotations

import os
from pathlib import Path

import reki


_ASSET_FILES = {
    "core": "ifs_eastasia_2026090712_f024.grib2",
    "time": "ifs_time_docdomain_2026090712.grib2",
    "ensemble": "ifs_ensemble_docdomain_2026090700.grib2",
    "layers": "ifs_layers_docdomain_2026090712.grib2",
    "global": "ifs_global_2026090712_f024.grib2",
}


def frozen_ifs_path(variant: str = "core") -> Path:
    """Return a checked-in-documentation-cache asset without downloading."""
    try:
        name = _ASSET_FILES[variant]
    except KeyError as error:
        raise ValueError(f"unknown documentation IFS variant: {variant!r}") from error
    cache_dir = Path(os.environ["REKI_TEST_DATA_DIR"])
    path = cache_dir / name
    if not path.is_file():
        raise RuntimeError("run `make -C doc data` before running documentation examples")
    return path



def open_ifs(variant: str = "core"):
    """Open a frozen local IFS asset through a public source declaration."""
    return reki.from_source({"kind": "file", "path": str(frozen_ifs_path(variant))})
