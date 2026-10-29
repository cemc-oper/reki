"""Explicit current-business registrations, with no availability discovery."""

import json
from pathlib import Path


def current_registration(catalog, dataset):
    """Only the selected builtin catalog activates these resource defaults.

    External catalog replacement never inherits a builtin product or layout.
    The current label is a business policy; exact resource bytes stay pinned.
    """
    filename = {
        "cma_gfs_gmf": "current-gfs.json",
        "cma_meso_3km": "current-meso3.json",
        "cma_meso_1km": "current-meso1.json",
        "cma_tym": "current-tym.json",
    }.get(dataset)
    if catalog.reference.get("builtin") != "reki.catalog" or filename is None:
        return None
    return json.loads((Path(__file__).with_name("builtin") / filename).read_text())
