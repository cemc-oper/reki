#!/usr/bin/env python3
"""Validate the frozen IFS documentation fixtures and their local cache."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import reki
from reki.sources.test import ECMWF_IFS_RELEASE_TAG


REQUIRED_VARIANTS = ("core", "time", "ensemble", "layers", "global")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_assets(cache_dir: Path) -> dict[str, Path]:
    manifest_path = cache_dir / f"ecmwf_ifs-{ECMWF_IFS_RELEASE_TAG}-manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"cached ecmwf_ifs manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assets = manifest.get("assets")
    if not isinstance(assets, dict):
        raise ValueError("manifest has no assets mapping")
    paths = {}
    for variant in REQUIRED_VARIANTS:
        asset = assets.get(variant)
        if not isinstance(asset, dict):
            raise ValueError(f"manifest is missing {variant!r}")
        path = cache_dir / asset.get("file", "")
        if not path.is_file():
            raise ValueError(f"cached {variant!r} asset is missing: {path}")
        if sha256(path) != asset.get("sha256"):
            raise ValueError(f"cached {variant!r} asset checksum does not match manifest")
        paths[variant] = path
    return paths


def assert_documentation_contract(paths: dict[str, Path], index_dir: Path) -> None:
    """Exercise real fixtures for G5/G6/G10/G11 and layer-bound examples."""
    for variant, path in paths.items():
        with reki.from_source({"kind": "file", "path": str(path)}) as source:
            fields = source.sel().all()
            assert len(fields), variant
            if variant == "core":
                assert len(fields) == 11
                data = source.sel(native={"grib": {"shortName": "2t"}}).one().to_xarray(rename="t2m")
                assert data.t2m.squeeze(drop=True).shape == (241, 361)
            if variant == "time":
                data = source.sel(native={"grib": {"shortName": "2t"}}).all().to_xarray(rename="t2m")
                assert list(data.step.values.astype("timedelta64[h]").astype(int)) == [0, 6, 12, 24]
                assert "valid_time" in data.coords
    # A path supplied to a protected reader is ignored without creating an index.
    from reki.format.grib import load_field_from_file
    import warnings
    before = sorted(index_dir.glob("*")) if index_dir.exists() else []
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        assert load_field_from_file(paths["core"], parameter="2t", with_index=str(index_dir / "retired.idx")) is not None
    assert len([w for w in captured if issubclass(w.category, FutureWarning)]) == 1
    assert (sorted(index_dir.glob("*")) if index_dir.exists() else []) == before


def assert_no_unmanaged_artifacts(doc_dir: Path, cache_dir: Path) -> None:
    forbidden = []
    # Sphinx writes executable notebook copies beneath doc/build; those are
    # build outputs, not source-tree residue. Only source files are guarded.
    for path in (doc_dir / "source").rglob("*"):
        if not path.is_file():
            continue
        if path.suffix in {".idx", ".sqlite", ".ipynb"}:
            forbidden.append(path)
    if forbidden:
        raise ValueError("unmanaged documentation artifacts: " + ", ".join(map(str, forbidden)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--index-dir", type=Path, required=True)
    parser.add_argument("--doc-dir", type=Path, required=True)
    args = parser.parse_args()
    paths = load_assets(args.cache_dir)
    assert_documentation_contract(paths, args.index_dir)
    assert_no_unmanaged_artifacts(args.doc_dir, args.cache_dir)
    print("IFS documentation fixtures, matrix cache, and artifact policy: OK")


if __name__ == "__main__":
    main()
