"""Explicit current-business registrations, with no availability discovery."""

import json
from pathlib import Path

_PROFILES = {
    "cma_gfs_gmf": "current-gfs.json",
    "cma_meso_3km": "current-meso3.json",
    "cma_meso_1km": "current-meso1.json",
    "cma_tym": "current-tym.json",
    "cma_geps": "current-geps.json",
    "cma_reps": "current-reps.json",
}


def current_registration(catalog, dataset):
    """Return the builtin native file layout and optional member numbering."""
    filename = _PROFILES.get(dataset)
    if catalog.reference.get("builtin") != "reki.catalog" or filename is None:
        return None
    return json.loads((Path(__file__).with_name("builtin") / filename).read_text())
