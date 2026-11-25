"""Read short names from the bundled wgrib2 NCEP naming tables."""

from collections import defaultdict
from functools import cache
from hashlib import sha256
from importlib.resources import files
import json

import eccodes

WGRIB2_NAME_KEY = "wgrib2Name"
_HEADER_KEYS = (
    "discipline",
    "parameterCategory",
    "parameterNumber",
    "tablesVersion",
    "centre",
    "localTablesVersion",
    "productionStatusOfProcessedData",
)
_LOCAL_GROUP = {98: "ecmwf_local", 78: "dwd_local", 79: "dwd_local"}


class _NameTables:
    def __init__(self, document, digest):
        self.tables = {}
        self.names = set()
        for group, rows in document["tables"].items():
            by_triple = defaultdict(list)
            for discipline, category, number, low, high, centre, local, name in rows:
                by_triple[discipline, category, number].append(
                    (low, high, centre, local, name)
                )
                self.names.add(name)
            self.tables[group] = by_triple
        upstream = document["upstream"]
        self.origin = (
            f"NOAA-EMC/wgrib2 {upstream['tag']} ({upstream['names']}, "
            f"{upstream['commit']}), names v{document['version']}, sha256={digest}"
        )

    def lookup(self, triple, master, centre, local, production_status):
        use_local = master == 255 or any(192 <= code <= 254 for code in triple)
        if use_local and local == 255:
            return None

        groups = ["ncep"]
        if production_status in (4, 5):
            groups.append("tigge")
        if use_local:
            groups.append(_LOCAL_GROUP.get(centre, "local"))

        for group in groups:
            rows = self.tables[group].get(triple, ())
            if use_local:
                # Each upstream table prefers the encoded local version and
                # then tries version 1, before going on to another table.
                for version in (local, 1):
                    for _, _, row_centre, row_local, name in rows:
                        if (centre, version) == (row_centre, row_local):
                            return name
            else:
                for low, high, _, _, name in rows:
                    if low <= master <= high:
                        return name
        return None


@cache
def _tables():
    data = files("reki.catalog").joinpath("builtin", "wgrib2-names.json").read_bytes()
    return _NameTables(json.loads(data), sha256(data).hexdigest())


def is_wgrib2_name(name):
    """Check whether the bundled naming tables contain this short name."""
    return name == name.upper() and name in _tables().names


def wgrib2_name_origin():
    return _tables().origin


def get_wgrib2_name(handle):
    """Return the uppercase wgrib2 NCEP short name for a GRIB2 handle, if known."""
    if eccodes.codes_get_long(handle, "edition") != 2:
        return None
    try:
        discipline, category, number, master, centre, local, status = (
            eccodes.codes_get_long(handle, key) for key in _HEADER_KEYS
        )
    except eccodes.KeyValueNotFoundError:
        return None
    return _tables().lookup((discipline, category, number), master, centre, local, status)
