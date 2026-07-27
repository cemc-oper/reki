from pathlib import Path

import pytest


# Tests in this directory call the CMADaaS MUSIC service, which needs a
# config file with credentials. Without the file, skip collection entirely;
# whether the service itself is reachable is probed at run time by the
# ``music_available`` fixture in the test module.
if not Path("~/.config/cedarkit.yaml").expanduser().exists():
    collect_ignore_glob = ["*"]


def pytest_collection_modifyitems(items):
    # NOTE: this hook fires for the whole session once any item below this
    # directory is collected, so filter by path before marking.
    here = Path(__file__).parent
    for item in items:
        if item.path.is_relative_to(here):
            item.add_marker(pytest.mark.cmadaas_service)
