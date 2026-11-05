"""Verify reviewed CEMC ORIG cases against unmodified source message bytes."""

import argparse
import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

import eccodes
import numpy as np
from cedarkit_query import normalize_query
from reki import from_source


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(array, dtype="<f8"):
    return sha256(np.ascontiguousarray(array, dtype=dtype)).hexdigest()


def original(case):
    with Path(case["file"]).open("rb") as stream:
        stream.seek(case["offset"])
        raw = stream.read(case["length"])
    require(len(raw) == case["length"], "truncated original")
    checksum = sha256(raw).hexdigest()
    require(case["record_sha256"] in {None, checksum}, "original SHA256 mismatch")
    handle = eccodes.codes_new_from_message(raw)
    try:
        for key, expected in case["native_match"].items():
            if not isinstance(expected, list):
                expected = [expected]
            require(
                eccodes.codes_get_long(handle, key) in expected, f"native {key} differs"
            )
        require(
            eccodes.codes_get_long(handle, "totalLength") == len(raw),
            "message length mismatch",
        )
        bitmap = eccodes.codes_get_long(handle, "bitmapPresent")
        marker = 1.0e300
        complex_missing = (
            not bitmap
            and eccodes.codes_is_defined(handle, "missingValueManagementUsed")
            and eccodes.codes_get_long(handle, "missingValueManagementUsed") in {1, 2}
        )
        if complex_missing:
            eccodes.codes_set_double(handle, "missingValue", marker)
        values = eccodes.codes_get_double_array(handle, "values")
        if bitmap:
            mask = eccodes.codes_get_long_array(handle, "bitmap") == 0
        elif complex_missing:
            mask = values == marker
        else:
            mask = np.zeros(values.size, dtype=bool)
        values[mask] = np.nan
        results = {
            "points": values.size,
            "missing": int(mask.sum()),
            "values_sha256": digest(values),
            "mask_sha256": digest(mask, "u1"),
        }
        del values, mask
        for name in ("latitude", "longitude"):
            results[f"{name}_sha256"] = digest(
                eccodes.codes_get_double_array(handle, name + "s")
            )
        return raw, checksum, results
    finally:
        eccodes.codes_release(handle)


def grid_hash(array, name):
    if "point" in array.dims:
        return digest(array[name].values)
    height, width = array.shape
    axis = array[name].values
    result = sha256()
    for start in range(0, height, 64):
        end = min(start + 64, height)
        values = axis[start:end, None] if name == "latitude" else axis[None, :]
        result.update(
            np.ascontiguousarray(
                np.broadcast_to(values, (end - start, width)), dtype="<f8"
            )
        )
    return result.hexdigest()


def verify(case, sample, *, mounted=False):
    raw, checksum, expected = original(case)
    if mounted:
        source = {"kind": "local", "root": "/CMADAAS", "dataset": case["dataset"]}
        path, offset = case["file"], case["offset"]
    else:
        sample.write_bytes(raw)
        source = {"kind": "file", "path": str(sample), "dataset": case["dataset"]}
        path, offset = str(sample), 0
    del raw
    query = normalize_query(case["query"]).to_dict()
    with from_source(source) as reader:
        field = reader.sel(case["query"]).one()
        identity = field.identity.to_dict()
        require(
            all(identity.get(k) == v for k, v in query.items()),
            "named identity differs",
        )
        require(
            case["mapping_id"] in field.metadata["mapping_ids"],
            "mapping identity differs",
        )
        location = field.metadata["source"]
        require(
            (location["path"], location["offset"]) == (path, offset),
            "selected file or record offset differs",
        )
        require(
            field.metadata.get("statistical_interval") == case["interval"],
            "statistical interval differs",
        )
        dataset = field.to_xarray()
        (name,) = dataset.data_vars
        data = dataset[name]
        require(
            data.attrs["cedarkit_parameter_id"] == query["parameter"],
            "Dataset parameter differs",
        )
        require(data.attrs["units"] == case["unit"], "Dataset unit differs")
        indices = {
            d: 0 for d in data.dims if d not in {"latitude", "longitude", "point"}
        }
        array = data.isel(indices, drop=True)
        mask = np.isnan(array.values)
        actual = {
            "points": array.size,
            "missing": int(mask.sum()),
            "values_sha256": digest(array.values),
            "mask_sha256": digest(mask, "u1"),
            **{f"{k}_sha256": grid_hash(array, k) for k in ("latitude", "longitude")},
        }
        require(
            actual == expected,
            f"whole-field comparison differs: {actual} != {expected}",
        )
        return {
            "id": case["id"],
            "file": case["file"],
            "offset": case["offset"],
            "sha256": checksum,
            "mapping_id": case["mapping_id"],
            "query": query,
            "source_kind": source["kind"],
            "unit": case["unit"],
            "interval": case["interval"],
            "definitions": field.report.to_dict()["context"]["definitions"],
            **actual,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path)
    parser.add_argument("--system", action="append")
    parser.add_argument(
        "--mounted",
        action="store_true",
        help="scan the complete mounted file instead of an isolated original record",
    )
    args = parser.parse_args()
    cases = [
        case
        for case in json.loads(args.cases.read_bytes())
        if not args.system or case["system"] in args.system
    ]
    if not cases:
        parser.error("no cases selected")
    failed = False
    with TemporaryDirectory(prefix="reki-orig-batch-") as temp:
        path = Path(temp) / "original.grib2"
        for case in cases:
            try:
                result = verify(case, path, mounted=args.mounted)
            except Exception as exc:  # noqa: BLE001 - preserve case failures and exit nonzero.
                failed = True
                result = {
                    "id": case["id"],
                    "status": "failed",
                    "error": str(exc),
                    "code": getattr(exc, "code", None),
                }
            else:
                result["status"] = "passed"
            print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
