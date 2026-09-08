#!/usr/bin/env python3
"""Execute standalone documentation examples and enforce their source contract."""

from __future__ import annotations

import argparse
import ast
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def assert_public_imports(path: Path) -> None:
    """Reject imports from private reki implementation modules."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        module = None
        if isinstance(node, ast.ImportFrom):
            module = node.module
        elif isinstance(node, ast.Import):
            for name in node.names:
                if name.name.startswith("reki.") and any(part.startswith("_") for part in name.name.split(".")):
                    raise ValueError(f"{path}: private reki import {name.name!r}")
        if module and module.startswith("reki.") and any(part.startswith("_") for part in module.split(".")):
            raise ValueError(f"{path}: private reki import {module!r}")


def run_example(path: Path, data_dir: Path) -> None:
    path = path.resolve()
    expected = path.with_suffix(".expected.json")
    if not expected.is_file():
        raise ValueError(f"{path}: missing fixed output {expected.name}")
    with tempfile.TemporaryDirectory(prefix="reki-doc-example-") as work_dir:
        environment = os.environ | {
            "REKI_TEST_DATA_DIR": str(data_dir),
            "REKI_INDEX_DIR": str(Path(work_dir) / "indexes"),
        }
        result = subprocess.run(
            [sys.executable, str(path)], cwd=work_dir, env=environment,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
    if result.returncode:
        raise ValueError(f"{path}: exited {result.returncode}\n{result.stderr}")
    if result.stdout != expected.read_text(encoding="utf-8"):
        raise ValueError(f"{path}: output differs from {expected.name}\n{result.stdout}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    examples = sorted(path for path in args.examples_dir.glob("*.py") if not path.name.startswith("_"))
    if not examples:
        raise SystemExit("no executable documentation examples found")
    for example in examples:
        assert_public_imports(example)
        run_example(example, args.data_dir)
    print(f"validated {len(examples)} documentation example(s)")


if __name__ == "__main__":
    main()
