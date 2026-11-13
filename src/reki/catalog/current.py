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


def current_registration(catalog, dataset, *, product=None):
    """Return the CEMC ORIG layout and member numbering for the catalog."""
    filename = _PROFILES.get(dataset)
    builtin = catalog.reference.get("builtin") == "reki.catalog"
    current_orig = product and (product["id"], product["version"]) == ("orig", "current")
    if (
        filename is None
        or catalog.value.id != "reki.cemc-catalog"
        or not (builtin or current_orig)
    ):
        return None
    return json.loads((Path(__file__).with_name("builtin") / filename).read_text())
