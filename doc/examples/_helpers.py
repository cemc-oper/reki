"""Shared helpers for deterministic, standalone documentation examples."""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import tempfile
from typing import Iterator

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


@contextmanager
def temporary_index() -> Iterator[Path]:
    """Yield an isolated index directory that is removed after the example."""
    with tempfile.TemporaryDirectory(prefix="reki-doc-index-") as directory:
        yield Path(directory)


def open_ifs(variant: str = "core", *, index_policy: str = "off", index_dir: Path | None = None):
    """Open a frozen local IFS asset with an explicit index policy."""
    kwargs = {"index_policy": index_policy}
    if index_dir is not None:
        kwargs["index_dir"] = index_dir
    return reki.from_source("file", frozen_ifs_path(variant), **kwargs)
