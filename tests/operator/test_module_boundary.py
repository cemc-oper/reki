"""Module boundary guard (doc section 11.5).

``reki/sources/`` and ``reki/readers/`` must not depend on
``reki/operator/``; operators only consume the unified data object
(``xarray.DataArray``) returned by readers.

The single allowed exception is the GRIB message-level wrapper package
``reki/readers/grib/eccodes/operator/`` (doc section 7.3), which adapts
the field-level operators to ecCodes message handles.
"""

import ast
from pathlib import Path

import reki

REKI_DIR = Path(reki.__file__).parent

# doc section 7.3: message-level extract_region/interpolate_grid stay
# inside the GRIB reader and adapt the field-level operators.
ALLOWED_OPERATOR_IMPORTERS = (
    REKI_DIR / "readers" / "grib" / "eccodes" / "operator",
)


def _operator_imports(module_path: Path) -> list[int]:
    """Line numbers of imports referencing reki.operator."""
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    lines = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "reki.operator" or alias.name.startswith("reki.operator."):
                    lines.append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level == 0 and (
                    module == "reki.operator"
                    or module.startswith("reki.operator.")
            ):
                lines.append(node.lineno)
    return lines


def test_sources_do_not_import_operator():
    offenders = []
    for path in (REKI_DIR / "sources").rglob("*.py"):
        lines = _operator_imports(path)
        if lines:
            offenders.append(f"{path.relative_to(REKI_DIR)}: lines {lines}")
    assert not offenders, (
        "reki/sources must not depend on reki/operator (doc 11.5):\n"
        + "\n".join(offenders)
    )


def test_readers_do_not_import_operator():
    offenders = []
    for path in (REKI_DIR / "readers").rglob("*.py"):
        if any(parent in path.parents or parent == path
               for parent in ALLOWED_OPERATOR_IMPORTERS):
            continue
        lines = _operator_imports(path)
        if lines:
            offenders.append(f"{path.relative_to(REKI_DIR)}: lines {lines}")
    assert not offenders, (
        "reki/readers must not depend on reki/operator (doc 11.5; "
        "only readers/grib/eccodes/operator is allowed, doc 7.3):\n"
        + "\n".join(offenders)
    )
