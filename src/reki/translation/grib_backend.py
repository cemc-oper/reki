"""Locate and decode original GRIB records using ecCodes native keys."""

from collections.abc import Mapping
from hashlib import sha256

import numpy as np
import xarray as xr

from cedarkit_query import Query, QueryError, SourceError
from cedarkit_query.normalize import _contains
from reki.catalog.model import thaw
from reki.selection.backend import Plan, FieldReference, BranchEvent
from reki.selection.core import key as identity_key, matches
from reki.selection.files import FileSnapshot, discover_paths
from reki.grib_io import decode_values
from . import grib
from .common import metadata_error, software_origin

INTEGER_KEYS = frozenset(
    {
        "edition",
        "centre",
        "subCentre",
        "tablesVersion",
        "localTablesVersion",
        "productionStatusOfProcessedData",
        "typeOfProcessedData",
        "typeOfGeneratingProcess",
        "discipline",
        "parameterCategory",
        "parameterNumber",
        "productDefinitionTemplateNumber",
        "typeOfFirstFixedSurface",
        "typeOfSecondFixedSurface",
        "scaleFactorOfFirstFixedSurface",
        "scaledValueOfFirstFixedSurface",
        "scaleFactorOfSecondFixedSurface",
        "scaledValueOfSecondFixedSurface",
        "year",
        "month",
        "day",
        "hour",
        "minute",
        "second",
        "significanceOfReferenceTime",
        "indicatorOfUnitOfTimeRange",
        "forecastTime",
        "numberOfTimeRange",
        "typeOfTimeIncrement",
        "indicatorOfUnitForTimeRange",
        "lengthOfTimeRange",
        "typeOfStatisticalProcessing",
        "derivedForecast",
        "probabilityType",
        "scaleFactorOfLowerLimit",
        "scaledValueOfLowerLimit",
        "scaleFactorOfUpperLimit",
        "scaledValueOfUpperLimit",
        "percentileValue",
        "yearOfEndOfOverallTimeInterval",
        "monthOfEndOfOverallTimeInterval",
        "dayOfEndOfOverallTimeInterval",
        "hourOfEndOfOverallTimeInterval",
        "minuteOfEndOfOverallTimeInterval",
        "secondOfEndOfOverallTimeInterval",
        "perturbationNumber",
        "typeOfEnsembleForecast",
        "numberOfForecastsInEnsemble",
        "backgroundProcess",
        "generatingProcessIdentifier",
        "forecastProbabilityNumber",
        "totalNumberOfForecastProbabilities",
    }
)
STRING_KEYS = frozenset(
    {"units", "parameterUnits", "gridType", "shortName", "packingType"}
)
NATIVE_KEYS = INTEGER_KEYS | STRING_KEYS
# Retain the remaining time-range descriptor fields as evidence, without
# claiming a sampling algorithm or widening the finite native Query selectors.
STATISTIC_EVIDENCE_KEYS = frozenset(
    {
        "indicatorOfUnitForTimeIncrement",
        "timeIncrement",
        "numberOfMissingInStatisticalProcess",
    }
)
# Raw evidence only; these do not expand the accepted native Query selectors.
GRID_INTEGER_KEYS = frozenset(
    {
        "gridDefinitionTemplateNumber",
        "shapeOfTheEarth",
        "Ni",
        "Nj",
        "numberOfDataPoints",
        "scanningMode",
        "iScansNegatively",
        "jScansPositively",
        "jPointsAreConsecutive",
        "alternativeRowScanning",
        "latitudeOfFirstGridPoint",
        "latitudeOfLastGridPoint",
        "longitudeOfFirstGridPoint",
        "longitudeOfLastGridPoint",
        "iDirectionIncrement",
        "jDirectionIncrement",
        "basicAngleOfTheInitialProductionDomain",
        "subdivisionsOfBasicAngle",
    }
)


def native_matches(metadata, condition):
    return all(
        k in metadata
        and metadata[k] is not None
        and (not isinstance(v, Mapping) or type(metadata[k]) in {int, float})
        and _contains(
            thaw(v),
            metadata[k],
            "number" if type(metadata[k]) in {int, float} else "literal",
        )
        for k, v in condition.items()
    )


def check_filter(condition):
    for key, value in condition.items():
        values = (
            value
            if isinstance(value, list)
            else list(value["range"].values())
            if isinstance(value, dict)
            else [value]
        )
        expected = int if key in INTEGER_KEYS else str if key in STRING_KEYS else None
        if expected is not None and any(type(v) is not expected for v in values):
            raise QueryError(
                "invalid_query",
                "/native/grib/" + key,
                "native key selector has the wrong scalar type",
            )


def _metadata(handle, *, keys=None):
    import eccodes

    result = {}
    for key in (
        NATIVE_KEYS | GRID_INTEGER_KEYS | STATISTIC_EVIDENCE_KEYS
        if keys is None
        else keys
    ):
        try:
            if (
                not eccodes.codes_is_defined(handle, key)
                or eccodes.codes_is_missing(handle, key)
                or eccodes.codes_get_size(handle, key) != 1
            ):
                result[key] = None
            else:
                result[key] = (
                    eccodes.codes_get_long(handle, key)
                    if key in INTEGER_KEYS | GRID_INTEGER_KEYS | STATISTIC_EVIDENCE_KEYS
                    else eccodes.codes_get(handle, key)
                )
        except (
            eccodes.KeyValueNotFoundError,
            eccodes.WrongTypeError,
            eccodes.ArrayTooSmallError,
        ):
            result[key] = None
    return result


_TIME_KEYS = {
    "year",
    "month",
    "day",
    "hour",
    "minute",
    "second",
    "forecastTime",
    *(
        part + "OfEndOfOverallTimeInterval"
        for part in ("year", "month", "day", "hour", "minute", "second")
    ),
}
_LEVEL_KEYS = {"scaleFactorOfFirstFixedSurface", "scaledValueOfFirstFixedSurface"}
_MEMBER_KEYS = {"perturbationNumber", "typeOfEnsembleForecast"}


def _coordinates(metadata, numbering, configuration):
    identity = {}
    interval = None
    # Generic coordinate projections are optional. Unknown local templates
    # and fixed-surface codes remain selectable by their encoded values.
    try:
        identity.update(grib.fixed_surfaces(metadata))
    except SourceError:
        pass
    try:
        times, interval = grib.time_fields(metadata)
        identity.update(times)
    except SourceError:
        pass
    if numbering:
        member = numbering.get(
            (metadata.get("typeOfEnsembleForecast"), metadata.get("perturbationNumber"))
        )
        if member is not None:
            identity.update(
                member=member, member_role=configuration.member_role(member)
            )
    return identity, interval


def _variable(metadata, identity):
    omit = set()
    if "time" in identity:
        omit.update(_TIME_KEYS)
    if "level" in identity:
        omit.update(_LEVEL_KEYS)
    if "member" in identity:
        omit.update(_MEMBER_KEYS)
    signature = {
        k: v for k, v in metadata.items() if k in INTEGER_KEYS and k not in omit
    }
    triple = "_".join(
        str(metadata.get(k, "x"))
        for k in ("discipline", "parameterCategory", "parameterNumber")
    )
    digest = sha256(identity_key(signature).encode()).hexdigest()[:16]
    return signature, f"grib_{triple}_{digest}"


class GribBackend:
    def __init__(self, configuration, *, numbering=None):
        self.configuration = configuration
        self.numbering = numbering

    def plan(self, queries, configuration):
        translations = []
        for qi, query in enumerate(queries):
            q = query.to_dict()
            native = q.get("native", {})
            if set(native) - {"grib"}:
                raise QueryError(
                    "unsupported", "/native", "file source accepts GRIB keys"
                )
            filters = native.get("grib", {})
            check_filter(filters)
            if {"member", "member_role"} & q.keys() and self.numbering is None:
                raise QueryError(
                    "unsupported", "/member", "use the native GRIB member keys"
                )
            translations.append(
                dict(
                    query_index=qi,
                    coverage=dict(
                        status="passed",
                        message="Scan original GRIB records with native predicates",
                    ),
                    branches=[
                        dict(
                            index=0,
                            backend="grib2",
                            scope={},
                            candidate_filter=filters,
                            residual=q,
                            basis=[],
                        )
                    ],
                    checks=[],
                )
            )
        return Plan(tuple(translations), tuple(None for _ in queries))

    def start(self, plan):
        return GribScan(self, plan)

    def close(self):
        pass


class GribScan:
    def __init__(self, backend, plan):
        self.backend, self.plan = backend, plan
        self.paths = discover_paths(
            backend.configuration,
            [t["branches"][0]["residual"] for t in plan.translations],
        )
        self.snapshots = []
        seen_files = set()
        for path in self.paths:
            try:
                snapshot = FileSnapshot.capture(path)
                if snapshot.fingerprint not in seen_files:
                    self.snapshots.append(snapshot)
                    seen_files.add(snapshot.fingerprint)
            except SourceError as exc:
                if (
                    backend.configuration.source["kind"] != "local"
                    or exc.code != "resource_not_found"
                ):
                    raise
        self.context = {
            "source": {
                "paths": [str(s.path) for s in self.snapshots],
                "fingerprints": {
                    str(s.path): list(s.fingerprint) for s in self.snapshots
                },
            }
        }
        import eccodes

        self.context["origins"] = {
            "adapter": software_origin("grib.native"),
            "native_library": "eccodes=" + eccodes.codes_get_api_version(),
        }
        self._iterator = None
        self.checks = {}
        self.keys = (
            NATIVE_KEYS
            | GRID_INTEGER_KEYS
            | STATISTIC_EVIDENCE_KEYS
            | {
                k
                for t in plan.translations
                for branch in t["branches"]
                for k in branch["candidate_filter"]
            }
        )

    def __iter__(self):
        self._iterator = self._fields()
        return self._iterator

    def close(self):
        if self._iterator is not None:
            self._iterator.close()

    def _fields(self):
        import eccodes
        from reki.grib_io import iter_headers, open_grib_file

        branches = [
            (t["query_index"], b) for t in self.plan.translations for b in t["branches"]
        ]
        for qi, b in branches:
            yield BranchEvent(qi, b["index"], "started")
        grids = {}
        for snapshot in self.snapshots:
            snapshot.verify()
            try:
                with open_grib_file(snapshot.path) as stream:
                    if stream.read(4) != b"GRIB":
                        raise SourceError(
                            "decode_failed",
                            "/source/path",
                            "explicit input is not a GRIB stream",
                        )
                iterator = iter_headers(snapshot.path)
                try:
                    for header in iterator:
                        snapshot.verify()
                        metadata = _metadata(header.handle, keys=self.keys)
                        native = {k: v for k, v in metadata.items() if v is not None}
                        candidates = [
                            (qi, b)
                            for qi, b in branches
                            if native_matches(native, b["candidate_filter"])
                        ]
                        if not candidates:
                            continue
                        identity, interval = _coordinates(
                            native, self.backend.numbering, self.backend.configuration
                        )
                        identity["native"] = {"grib": native}
                        links = [
                            (qi, b["index"])
                            for qi, b in candidates
                            if matches(identity, thaw(b["residual"]))
                        ]
                        if not links:
                            continue
                        grid_id = eccodes.codes_get_string(
                            header.handle, "md5GridSection"
                        )
                        if grid_id not in grids:
                            grids[grid_id] = _grid(header.handle, grid_id)
                        grid, coords, dims, shape = grids[grid_id]
                        offset = header.offset
                        signature, name = _variable(native, identity)
                        meta = dict(
                            source={
                                "path": str(snapshot.path),
                                "offset": offset,
                                "fingerprint": list(snapshot.fingerprint),
                            },
                            native_fields=native,
                            native_variable=signature,
                            native_name=name,
                            vertical_definition={"id": "WMO.GRIB2.fixed-surfaces"},
                        )
                        if interval is not None:
                            meta["statistical_interval"] = interval
                        yield FieldReference(
                            repr((snapshot.fingerprint, offset)),
                            Query(identity),
                            meta,
                            grid,
                            lambda s=snapshot, o=offset, c=coords, d=dims, sh=shape: (
                                _load(s, o, c, d, sh)
                            ),
                            tuple(links),
                        )
                finally:
                    iterator.close()
                snapshot.verify()
            except eccodes.CodesInternalError as exc:
                raise SourceError(
                    "decode_failed", "", "ecCodes header decoding failed"
                ) from exc
            except PermissionError as exc:
                raise SourceError(
                    "permission_denied",
                    "/source/path",
                    "cannot read explicit GRIB input",
                ) from exc
            except OSError as exc:
                raise SourceError(
                    "io_error", "/source/path", "GRIB input access failed"
                ) from exc
        for qi, b in branches:
            yield BranchEvent(qi, b["index"], "exhausted")


def _grid(handle, definition):
    import eccodes

    # Keep the ecCodes scan order. Independent regular axes use a 2-D
    # representation. Other geometries keep one coordinate pair per point.
    lat = eccodes.codes_get_double_array(handle, "latitudes")
    lon = eccodes.codes_get_double_array(handle, "longitudes")
    points = eccodes.codes_get_long(handle, "numberOfDataPoints")
    if lat.size != points or lon.size != points:
        metadata_error(
            "inconsistent_native_metadata", "grid coordinates and point count disagree"
        )
    if not np.isfinite(lat).all() or not np.isfinite(lon).all():
        metadata_error(
            "inconsistent_native_metadata", "grid coordinates must be finite"
        )
    grid = {"definition": definition, "points": points}
    dimensions = _metadata(handle, keys=("Ni", "Nj"))
    ni, nj = dimensions["Ni"], dimensions["Nj"]
    if (
        ni
        and nj
        and ni * nj == points
        and not (
            eccodes.codes_get_long(handle, "jPointsAreConsecutive")
            or eccodes.codes_get_long(handle, "alternativeRowScanning")
        )
    ):
        lat2, lon2 = lat.reshape(nj, ni), lon.reshape(nj, ni)
        if np.all(lat2 == lat2[:, :1]) and np.all(lon2 == lon2[:1, :]):
            return (
                grid,
                {"latitude": lat2[:, 0].copy(), "longitude": lon2[0].copy()},
                ("latitude", "longitude"),
                (nj, ni),
            )
    return (
        grid,
        {"latitude": ("point", lat), "longitude": ("point", lon)},
        ("point",),
        (points,),
    )


def _load(snapshot, offset, coords, dims, shape):
    import eccodes
    from reki.grib_io import load_message_at_offset

    def decode():
        handle = load_message_at_offset(snapshot.path, offset)
        if handle is None:
            raise SourceError(
                "decode_failed", "", "record offset no longer identifies a message"
            )
        try:
            values = decode_values(handle).reshape(shape)
            return xr.DataArray(values, dims=dims, coords=coords)
        except eccodes.CodesInternalError as exc:
            raise SourceError(
                "decode_failed", "", "ecCodes value decoding failed"
            ) from exc
        finally:
            eccodes.codes_release(handle)

    return snapshot.load(decode)
