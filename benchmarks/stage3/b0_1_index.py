"""Stage-3 B0-1 indexed GRIB benchmark.

Run from ``repo/reki``::

    uv run python benchmarks/stage3/b0_1_index.py OUT.json --runs 5

The benchmark always uses an explicitly supplied temporary index root.  It
therefore never reads, deletes, or measures a developer's normal cache.
"""

import argparse
import hashlib
import json
import multiprocessing
import platform
import resource
import shutil
import statistics
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

import eccodes
import reki
from reki.diagnostics import collect_io_metrics
from reki.readers.grib.index import IndexStore


DATA = Path(__file__).parents[2] / "tests/data/gfs_basic/Z_NAFP_C_BABJ_20260716000000_P_NWPC-GRAPES-GFS-GLB-02400.grib2"
QUERIES = [
    {"parameter": "2t", "level_type": "heightAboveGround", "level": 2},
    {"parameter": "t", "level_type": "pl", "level": 850},
    {"parameter": "t", "level_type": "pl", "level": 500},
    {"parameter": "u", "level_type": "pl", "level": 850},
    {"parameter": "v", "level_type": "pl", "level": 850},
    {"parameter": "gh", "level_type": "pl", "level": 500},
    {"parameter": "r", "level_type": "pl", "level": 850},
    {"parameter": "msl", "level_type": "sfc"},
    {"parameter": "tp", "level_type": "sfc"},
    {"parameter": "10u", "level_type": "heightAboveGround", "level": 10},
]


def _measure(index_dir, policy, *, batched=False):
    """Run the fixed B0-1 workload and return timing plus official counters."""
    tracemalloc.start()
    started = time.perf_counter()
    with collect_io_metrics() as metrics:
        reader = reki.from_source("file", DATA, index_policy=policy, index_dir=index_dir)
        if batched:
            fields = reader.fetch_many(QUERIES, cardinality="first")
        else:
            fields = [reader.sel(**query).first() for query in QUERIES]
        hits = sum(field is not None for field in fields)
        for field in fields:
            if field is not None:
                field.to_xarray().values
        snapshot = metrics.snapshot().to_dict()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    index_path = IndexStore(DATA, index_dir=index_dir).path
    return {
        "wall_time_seconds": time.perf_counter() - started,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "python_peak_bytes": peak,
        "query_match_count": hits,
        "index_file_bytes": index_path.stat().st_size if index_path.exists() else 0,
        **snapshot,
    }


def _summary(runs):
    times = [run["wall_time_seconds"] for run in runs]
    return {"wall_time_seconds": {"min": min(times), "median": statistics.median(times), "max": max(times)}}


def _concurrent_worker(index_dir, queue):
    try:
        result = _measure(index_dir, "auto")
        queue.put({"ok": True, "result": result})
    except Exception as error:  # pragma: no cover - surfaced by parent assertion
        queue.put({"ok": False, "error": repr(error)})


def _concurrent(index_dir, workers=2):
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    processes = [context.Process(target=_concurrent_worker, args=(str(index_dir), queue))
                 for _ in range(workers)]
    for process in processes:
        process.start()
    results = [queue.get(timeout=120) for _ in processes]
    for process in processes:
        process.join(120)
    if any(process.exitcode != 0 for process in processes) or not all(row["ok"] for row in results):
        raise RuntimeError(f"concurrent index build failed: {results!r}")
    store = IndexStore(DATA, index_dir=index_dir)
    connection = store.open_valid()
    valid = connection is not None
    if connection is not None:
        connection.close()
    return {"workers": workers, "valid_index": valid,
            "runs": [row["result"] for row in results]}


def _environment():
    return {
        "python": sys.version.split()[0], "platform": platform.platform(),
        "eccodes": str(eccodes.codes_get_api_version()),
        "reki": getattr(reki, "__version__", "editable"),
        "data_sha256": hashlib.sha256(DATA.read_bytes()).hexdigest(),
    }


def main(output, runs):
    if not DATA.is_file():
        raise SystemExit(f"fixed test data missing: {DATA}")
    root = Path(tempfile.mkdtemp(prefix="reki-stage3-b0-1-"))
    try:
        # Each scenario has an independent explicit cache root.  The first
        # unrecorded run avoids importing and decoder initialisation skew.
        off_root, cold_root, hot_root, batch_root, corrupt_root, concurrent_root = (
            root / name for name in ("off", "cold", "hot", "batch", "corrupt", "concurrent")
        )
        _measure(off_root, "off")
        off = [_measure(off_root, "off") for _ in range(runs)]

        cold = []
        for _ in range(runs):
            shutil.rmtree(cold_root, ignore_errors=True)
            cold.append(_measure(cold_root, "auto"))

        _measure(hot_root, "auto")
        hot = [_measure(hot_root, "readonly") for _ in range(runs)]

        _measure(batch_root, "auto", batched=True)
        batch = [_measure(batch_root, "readonly", batched=True) for _ in range(runs)]

        corrupt = []
        for _ in range(runs):
            shutil.rmtree(corrupt_root, ignore_errors=True)
            _measure(corrupt_root, "auto")
            IndexStore(DATA, index_dir=corrupt_root).path.write_bytes(b"not sqlite")
            corrupt.append(_measure(corrupt_root, "auto"))

        concurrent = _concurrent(concurrent_root)
        result = {
            "schema_version": 1,
            "scenario": "stage-3 B0-1 index policies",
            "profile": "offline-required",
            "environment": _environment(),
            "queries": QUERIES,
            "scenarios": {
                "off": {"runs": off, "summary": _summary(off)},
                "cold": {"runs": cold, "summary": _summary(cold)},
                "hot": {"runs": hot, "summary": _summary(hot)},
                "batch_hot": {"runs": batch, "summary": _summary(batch)},
                "corrupt_recovery": {"runs": corrupt, "summary": _summary(corrupt)},
                "concurrent_first_access": concurrent,
            },
            "note": "All index roots were temporary and removed after this run.",
        }
        Path(output).write_text(json.dumps(result, indent=2) + "\n")
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--runs", type=int, default=5)
    arguments = parser.parse_args()
    main(arguments.output, arguments.runs)
