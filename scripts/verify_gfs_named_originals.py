"""Verify the two task 05 GFS queries against frozen original GRIB2 bytes."""

import argparse
import json
from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory

import cedarkit_query
import eccodes
import numpy as np
import reki
from cedarkit_query import QueryReport, Request
from reki import from_source

RELATIVE_PATH = (
    "DATA/NAFP/NMC/GRAPES-GFS-GLB/2026/20261102/"
    "Z_NAFP_C_BABJ_20261102120000_P_NWPC-GRAPES-GFS-GLB-00600.grib2"
)
FILE_SIZE = 1_453_111_429
ORIGIN = "2026-11-02T12:00:00Z"
VALID = "2026-11-02T18:00:00Z"
GRID_SHAPE = (1440, 2880)


@dataclass(frozen=True)
class Case:
    name: str
    axis: str
    level: int
    surface: int
    offset: int
    length: int
    digest: str

    @property
    def parameter(self):
        return f"cedarkit.{self.name}"

    def query(self):
        query = {"parameter": self.parameter, "time": ORIGIN, "step": "PT6H"}
        if self.axis == "pressure":
            query.update(level_type="pressure", level=self.level, level_unit="hPa")
        return query


CASES = (
    Case(
        "t2m",
        "height_above_ground",
        2,
        103,
        64322725,
        2414519,
        "76c4f3e504c8f457b684f3fd974b1ed5b5f253da6a3d5e98cc2a1b0966f5dd7b",
    ),
    Case(
        "t",
        "pressure",
        850,
        100,
        223415206,
        1980449,
        "b4560f6692c22ef33b585adc445ce646b71bc082403082e13b32e7170e4dac80",
    ),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest_array(array, dtype="<f8"):
    return sha256(np.ascontiguousarray(array, dtype=dtype)).hexdigest()


def read_oracle(path, case):
    """Decode the frozen byte range directly, without reki selection or decoding."""
    with path.open("rb") as stream:
        stream.seek(case.offset)
        raw = stream.read(case.length)
    require(
        len(raw) == case.length and sha256(raw).hexdigest() == case.digest,
        f"{case.name}: frozen original SHA256 or length mismatch",
    )
    handle = eccodes.codes_new_from_message(raw)
    try:
        header = {
            "edition": 2,
            "discipline": 0,
            "parameterCategory": 0,
            "parameterNumber": 0,
            "productDefinitionTemplateNumber": 0,
            "typeOfFirstFixedSurface": case.surface,
            "typeOfSecondFixedSurface": 255,
            "scaleFactorOfFirstFixedSurface": 0,
            "scaledValueOfFirstFixedSurface": case.level
            * (100 if case.axis == "pressure" else 1),
            "dataDate": 20261102,
            "dataTime": 1200,
            "forecastTime": 6,
            "indicatorOfUnitOfTimeRange": 1,
            "Nj": GRID_SHAPE[0],
            "Ni": GRID_SHAPE[1],
        }
        for key, expected in header.items():
            require(
                eccodes.codes_get_long(handle, key) == expected,
                f"{case.name}: original header {key} differs",
            )
        require(
            eccodes.codes_get_string(handle, "units") == "K",
            f"{case.name}: original unit is not K",
        )
        bitmap = eccodes.codes_get_long(handle, "bitmapPresent")
        marker = 1.0e300
        complex_missing = (
            not bitmap
            and eccodes.codes_is_defined(handle, "missingValueManagementUsed")
            and eccodes.codes_get_long(handle, "missingValueManagementUsed") in (1, 2)
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
        lat, lon = (
            eccodes.codes_get_double_array(handle, name).reshape(GRID_SHAPE)
            for name in ("latitudes", "longitudes")
        )
        return values.reshape(GRID_SHAPE), mask.reshape(GRID_SHAPE), lat, lon
    finally:
        eccodes.codes_release(handle)


def verify_field(field, path, case, oracle):
    location = field.metadata["source"]
    require(
        location["path"] == str(path) and location["offset"] == case.offset,
        f"{case.name}: reki selected a different file or byte offset",
    )
    require(
        field.identity.parameter == case.parameter
        and field.identity.level == case.level,
        f"{case.name}: selected identity differs",
    )
    report = field.report.to_dict()
    require(
        report["overall"]["status"] == "complete"
        and report["overall"]["field_count"] == 1,
        f"{case.name}: unexpected completeness report",
    )
    ds = field.to_xarray()
    require(
        QueryReport.from_json(ds.attrs["cedarkit_query_report"]) == field.report,
        f"{case.name}: Dataset report differs from field report",
    )
    array = ds[case.name]
    require(
        array.dims == ("time", "step", case.axis, "latitude", "longitude")
        and array.shape == (1, 1, 1, *GRID_SHAPE),
        f"{case.name}: Dataset dimensions differ",
    )
    require(
        array.attrs["cedarkit_parameter_id"] == case.parameter
        and array.attrs["units"] == field.metadata["source_unit"] == "K"
        and ds[case.axis].item() == case.level,
        f"{case.name}: Dataset parameter, level or units differ",
    )
    np.testing.assert_array_equal(
        ds.time.values, np.array([ORIGIN[:-1]], dtype="datetime64[ns]")
    )
    np.testing.assert_array_equal(ds.step.values, np.array([6], dtype="timedelta64[h]"))
    np.testing.assert_array_equal(
        ds.valid_time.values, np.array([[VALID[:-1]]], dtype="datetime64[ns]")
    )
    actual = array.values[0, 0, 0]
    values, mask, lat, lon = oracle
    np.testing.assert_array_equal(np.isnan(actual), mask)
    np.testing.assert_array_equal(actual, values)
    np.testing.assert_array_equal(
        np.broadcast_to(ds.latitude.values[:, None], GRID_SHAPE), lat
    )
    np.testing.assert_array_equal(
        np.broadcast_to(ds.longitude.values[None, :], GRID_SHAPE), lon
    )
    return report, list(location["fingerprint"])


def verify_case(source, path, case):
    oracle = read_oracle(path, case)
    query = case.query()
    with from_source(source) as reader:
        direct = reader.sel(**query).one(completeness="required")
        report, fingerprint = verify_field(direct, path, case, oracle)
    with TemporaryDirectory(prefix="reki-gfs-request-") as directory:
        for suffix in (".json", ".yaml"):
            request_path = Path(directory) / ("query" + suffix)
            Request.from_dict(
                {
                    "api_version": "cedarkit.request/v1",
                    "source": source,
                    "queries": [
                        {
                            **query,
                            "parameter": case.name
                            if suffix == ".yaml"
                            else case.parameter,
                        }
                    ],
                    "completeness": "required",
                }
            ).dump(request_path)
            request = Request.load(request_path)
            with from_source(request.source, context=request.context) as reader:
                field = reader.sel(request.queries).one(
                    completeness=request.completeness
                )
                actual_report, actual_fingerprint = verify_field(
                    field, path, case, oracle
                )
            require(
                (actual_report, actual_fingerprint) == (report, fingerprint),
                f"{case.name}: Request and Python results differ",
            )
    values, mask, lat, lon = oracle
    return {
        "query": query,
        "offset": case.offset,
        "length": case.length,
        "message_sha256": case.digest,
        "file_fingerprint": fingerprint,
        "values_sha256": digest_array(values),
        "mask_sha256": digest_array(mask, "u1"),
        "latitude_sha256": digest_array(lat),
        "longitude_sha256": digest_array(lon),
        "missing_points": int(mask.sum()),
        "report": report,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/CMADAAS"))
    args = parser.parse_args()
    root = args.root.resolve()
    path = root / RELATIVE_PATH
    if not path.is_file():
        parser.error(f"frozen original is unavailable: {path}")
    require(path.stat().st_size == FILE_SIZE, f"frozen file size mismatch: {path}")
    source = {"kind": "local", "dataset": "cma_gfs_gmf", "root": str(root)}
    results = [verify_case(source, path, case) for case in CASES]
    print(
        json.dumps(
            {
                "path": str(path),
                "file_size": FILE_SIZE,
                "cases": results,
                "reki": {"version": version("reki"), "module": reki.__file__},
                "cedarkit_query": {
                    "version": version("cedarkit-query"),
                    "module": cedarkit_query.__file__,
                },
                "eccodes": eccodes.codes_get_api_version(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
