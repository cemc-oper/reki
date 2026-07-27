from pathlib import Path

import pytest


# Tests in this directory use the mounted CMADaaS disk tree (/CMADAAS).
# Skip collection entirely when it is not mounted.
if not Path("/CMADAAS").exists():
    collect_ignore_glob = ["*"]


def pytest_collection_modifyitems(items):
    # NOTE: this hook fires for the whole session once any item below this
    # directory is collected, so filter by path before marking.
    here = Path(__file__).parent
    for item in items:
        if item.path.is_relative_to(here):
            item.add_marker(pytest.mark.cmadaas_local)
