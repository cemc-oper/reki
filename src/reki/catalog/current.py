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
    """Only the selected builtin catalog activates these resource defaults.

    External catalog replacement never inherits a builtin product or layout.
    The current label is a business policy; exact resource bytes stay pinned.
    """
    filename = _PROFILES.get(dataset)
    if catalog.reference.get("builtin") != "reki.catalog" or filename is None:
        return None
    return json.loads((Path(__file__).with_name("builtin") / filename).read_text())


def current_member_numbering(configuration):
    """Exact internal joint numbering, activated by the builtin product only.

    These reviewed entries preserve native positive/negative perturbation kinds.
    External catalogs and anonymous files do not inherit a numbering contract.
    """
    if configuration.origins.get("product_selection") != "builtin.current-business":
        return None
    filename = _PROFILES.get(configuration.source.get("dataset"))
    if filename is None:
        return None
    profile = json.loads((Path(__file__).with_name("builtin") / filename).read_text())
    if "member_numbering" not in profile:
        return None
    return {
        (row["typeOfEnsembleForecast"], row["perturbationNumber"]): row["member"]
        for row in profile["member_numbering"]
    }
