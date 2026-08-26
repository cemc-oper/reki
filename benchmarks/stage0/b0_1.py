"""Stage-0 B0-1: repeatable real-GRIB query baseline.

Run from ``repo/reki``: ``uv run python benchmarks/stage0/b0_1.py OUT.json``.
"""
import json
import resource
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

import reki


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


def measure():
    tracemalloc.start()
    started = time.perf_counter()
    decoded = 0
    reader = reki.from_source("file", DATA)
    for query in QUERIES:
        field = reader.sel(**query).first()
        if field is not None:
            field.to_xarray().values
            decoded += 1
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {"wall_time_seconds": time.perf_counter() - started,
            "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
            "python_peak_bytes": peak, "file_open_count": None,
            "grib_header_scan_count": None, "value_decode_count": decoded,
            "figure_count": 0, "output_bytes": 0}


def main(output):
    if not DATA.is_file():
        raise SystemExit(f"fixed test data missing: {DATA}")
    measure()  # warm-up, intentionally omitted
    runs = [measure() for _ in range(5)]
    times = [run["wall_time_seconds"] for run in runs]
    Path(output).write_text(json.dumps({"scenario": "B0-1", "profile": "offline-required",
        "queries": QUERIES, "runs": runs,
        "summary": {"wall_time_seconds": {"min": min(times), "median": statistics.median(times), "max": max(times)}}}, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
