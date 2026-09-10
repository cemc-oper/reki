"""Fail when a supported public export is absent from the API inventory or HTML.

The check intentionally reads source with ``ast`` rather than importing reki:
documentation validation must not perform remote source I/O or depend on an
optional backend being importable.  The module-to-page map is the reviewed
public surface from ``public-api-inventory.md``; add a module deliberately
when its exports become supported.
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
import sys


MODULE_PAGES = {
    "reki/__init__.py": "top-level.html",
    "reki/core/__init__.py": "core.html",
    "reki/sources/__init__.py": "sources.html",
    "reki/readers/__init__.py": "readers.html",
    "reki/catalog/__init__.py": "catalog.html",
    "reki/readers/grib/config/__init__.py": "grib.html",
    "reki/format/grib/__init__.py": "legacy.html",
    "reki/format/grib/cfgrib/__init__.py": "legacy.html",
    "reki/format/grib/common/__init__.py": "legacy.html",
    "reki/format/grib/eccodes/__init__.py": "legacy.html",
    "reki/format/grib/eccodes/bytes.py": "legacy.html",
    "reki/format/grib/eccodes/operator/__init__.py": "legacy.html",
    "reki/format/grib/config/__init__.py": "legacy.html",
    "reki/format/grads/__init__.py": "legacy.html",
    "reki/format/netcdf/__init__.py": "legacy.html",
    "reki/format/table/__init__.py": "legacy.html",
}


def exported_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
            continue
        if not isinstance(node.value, (ast.List, ast.Tuple)):
            raise ValueError(f"{path}: __all__ must be a literal list or tuple")
        values = []
        for value in node.value.elts:
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                raise ValueError(f"{path}: __all__ contains a non-string value")
            values.append(value.value)
        return values
    raise ValueError(f"{path}: expected an explicit __all__")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--html-root", type=Path, required=True)
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    source_root = repo / "src"
    inventory = args.inventory.read_text(encoding="utf-8")
    failures = []
    pages: dict[str, str] = {}

    for relative_path, page_name in MODULE_PAGES.items():
        page = args.html_root / "development" / "api" / page_name
        if page_name not in pages:
            pages[page_name] = page.read_text(encoding="utf-8")
        for symbol in exported_names(source_root / relative_path):
            marker = f"`{symbol}`"
            if marker not in inventory:
                failures.append(f"{relative_path}: {symbol} is missing from the public API inventory")
            if symbol not in pages[page_name]:
                failures.append(f"{relative_path}: {symbol} is missing from API page {page_name}")

    if failures:
        print("Public API documentation coverage failed:", file=sys.stderr)
        print("\n".join(f"- {failure}" for failure in failures), file=sys.stderr)
        return 1
    print("Public API documentation coverage passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
