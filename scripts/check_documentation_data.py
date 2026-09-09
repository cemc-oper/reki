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


def reader(path: Path, **kwargs):
    return reki.from_source("file", path, **kwargs)


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
    core = reader(paths["core"], index_policy="off")
    assert core.sel(
        parameter="2t", level_type="heightAboveGround", level=2,
    ).first() is not None

    time = reader(paths["time"], index_policy="off")
    time_data = time.sel(
        parameter="2t", level_type="heightAboveGround", level=2, step=[0, 6, 12, 24],
    ).to_xarray()
    assert list(time_data.step.values.astype("timedelta64[h]").astype(int)) == [0, 6, 12, 24]
    assert "valid_time" in time_data.coords
    accumulated = time.sel(
        parameter="tp", level_type="surface", level=0, step=24,
    ).all().one()
    assert accumulated.metadata.step_type == "accum"
    assert accumulated.metadata.time_range.total_seconds() == 24 * 60 * 60

    ensemble = reader(paths["ensemble"], index_policy="off")
    ensemble_data = ensemble.sel(
        parameter="2t", level_type="heightAboveGround", level=2, step=24,
    ).to_xarray()
    assert list(ensemble_data.number.values) == list(range(21))

    layers = reader(paths["layers"], index_policy="off")
    layer_data = layers.sel(parameter="sot", level_type="soilLayer", level=[1, 2]).to_xarray()
    assert list(layer_data.soilLayer.values) == [1, 2]
    assert layer_data.soilLayer_bounds.values.tolist() == [[0, 1], [1, 2]]

    indexed = reader(paths["core"], index_policy="auto", index_dir=index_dir)
    assert len(indexed.ls()) == 11
    assert list(index_dir.glob("*.sqlite")), "G10 index fixture was not created"


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
