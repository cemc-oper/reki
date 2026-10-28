"""ecCodes-only backend for explicit local files and finite standard GRIB2 paths.

No business catalog/mapping defaults are supplied. Product-specific numbering,
vertical definitions and independent expected domains require explicit proven
internal bindings; these are never inferred from paths or observed records.
"""

import numpy as np
import xarray as xr

from cedarkit_query import (
    Query,
    QueryError,
    SourceError,
    expand_queries,
    validate_rule,
    constrain_query,
)
from cedarkit_query.normalize import _contains, _count
from reki.catalog.model import thaw, freeze
from reki.selection.backend import Plan, FieldReference, BranchEvent
from reki.selection.core import matches, expected_from_domain
from reki.selection.files import FileSnapshot, discover_paths
from reki.diagnostics import record_io_event
from . import grib
from .common import metadata_error, unsupported, value_unit, software_origin

INTEGER_KEYS = frozenset(
    {
        "edition",
        "centre",
        "subCentre",
        "tablesVersion",
        "localTablesVersion",
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
    }
)
STRING_KEYS = frozenset({"units", "parameterUnits", "gridType"})
NATIVE_KEYS = INTEGER_KEYS | STRING_KEYS


def native_matches(metadata, condition):
    return all(
        k in metadata
        and metadata[k] is not None
        and _contains(v, metadata[k], "number" if k in INTEGER_KEYS else "literal")
        for k, v in condition.items()
    )


def check_filter(condition):
    for key, value in condition.items():
        if key not in NATIVE_KEYS:
            unsupported(
                "native key is not registered by this finite backend", native_key=key
            )
        values = (
            value
            if isinstance(value, list)
            else list(value["range"].values())
            if isinstance(value, dict)
            else [value]
        )
        expected = int if key in INTEGER_KEYS else str
        if any(type(v) is not expected for v in values) or (
            expected is str and isinstance(value, dict)
        ):
            raise QueryError(
                "invalid_query",
                "/native/grib/" + key,
                "native key selector has the wrong scalar type",
            )
        if key in {
            "edition",
            "productDefinitionTemplateNumber",
            "tablesVersion",
            "localTablesVersion",
        }:
            allowed = {
                "edition": {2},
                "tablesVersion": {4},
                "localTablesVersion": {0},
            }.get(key, grib.TEMPLATES)
            count = _count(value, "number")
            if count is None:
                count = value["range"]["end"] - value["range"]["start"] + 1
            if sum(_contains(value, v, "number") for v in allowed) != count:
                unsupported(
                    "query requests an unregistered edition or template", native_key=key
                )


def _metadata(handle):
    import eccodes

    result = {}
    for key in NATIVE_KEYS:
        try:
            if not eccodes.codes_is_defined(handle, key) or eccodes.codes_is_missing(
                handle, key
            ):
                result[key] = None
            else:
                result[key] = (
                    eccodes.codes_get_long(handle, key)
                    if key in INTEGER_KEYS
                    else eccodes.codes_get_string(handle, key)
                )
        except eccodes.KeyValueNotFoundError:
            result[key] = None
    return result


class GribBackend:
    def __init__(
        self,
        configuration,
        *,
        numbering=None,
        vertical_definition=None,
        expected_domain=None,
        identity_fields=(),
        quantity_kinds=None,
    ):
        self.configuration = configuration
        self.numbering = None if numbering is None else freeze(numbering)
        self.vertical_definition = freeze(vertical_definition)
        self.expected_domain = freeze(expected_domain)
        self.identity_fields = tuple(identity_fields)
        self.quantity_kinds = freeze({} if quantity_kinds is None else quantity_kinds)

    def _mappings(self, query):
        config = self.configuration
        parameter = query.to_dict().get("parameter")
        if parameter is None:
            return []
        names = parameter if isinstance(parameter, list) else [parameter]
        selected = []
        known = config.report_context()["source"]
        for resource in config.resources.mappings:
            if resource["backend"] != "grib2":
                continue
            for mapping in resource["mappings"]:
                if mapping["parameter_id"] not in names:
                    continue
                scope = thaw(mapping["applies_to"])
                for key in ("dataset", "product", "product_version"):
                    if key in scope and key not in known:
                        raise QueryError(
                            "invalid_config",
                            "/context",
                            "mapping requires exact source/product identity",
                            {"reason": "missing_context"},
                        )
                if any(
                    not _contains(scope[k], known[k], "literal")
                    for k in ("dataset", "product", "product_version")
                    if k in scope
                ):
                    continue
                selected.append((resource, mapping))
        return selected

    def plan(self, queries, configuration):
        translations = []
        for qi, query in enumerate(queries):
            q = query.to_dict()
            check_filter(q.get("native", {}).get("grib", {}))
            if {"member", "member_role"} & q.keys() and self.numbering is None:
                unsupported(
                    "canonical member selection needs an exact numbering contract",
                    query_index=qi,
                )
            mappings = self._mappings(query)
            branches = []
            if "parameter" in q:
                if not mappings:
                    raise QueryError(
                        "unsupported",
                        "/queries",
                        "no exact GRIB mapping covers this parameter",
                        {"reason": "mapping_coverage_gap", "query_index": qi},
                    )
                cover = []
                for resource, mapping in mappings:
                    native = thaw(mapping["native"]["match"])
                    check_filter(native)
                    for duty, rule in mapping["native"].get("translate", {}).items():
                        validate_rule(rule, backend="grib2", responsibility=duty)
                    condition = thaw(mapping["when"])
                    if "native" in condition:
                        unsupported(
                            "native predicates in mapping.when need a composed finite path",
                            query_index=qi,
                        )
                    if "time" in mapping["applies_to"]:
                        condition = constrain_query(
                            condition, {"time": thaw(mapping["applies_to"]["time"])}
                        ).to_dict()
                    # Parameter identity is exact; descendant mappings are never inherited.
                    condition = {"parameter": mapping["parameter_id"], **condition}
                    cover.append(condition)
                    branches.append(
                        dict(
                            index=len(branches),
                            backend="grib2",
                            scope={
                                k: thaw(v) for k, v in mapping["applies_to"].items()
                            },
                            candidate_filter=native,
                            residual={**q},
                            basis=[
                                dict(
                                    kind="mapping",
                                    resource={"kind": "mappings", "id": resource["id"]},
                                    mapping=mapping["id"],
                                ),
                                dict(
                                    kind="definition",
                                    resource={
                                        "kind": "parameters",
                                        "id": configuration.resources.parameters["id"],
                                    },
                                    parameter_id=mapping["parameter_id"],
                                ),
                            ],
                        )
                    )
                # A compact predicate containing the whole Query proves coverage
                # without enumerating open coordinates. Otherwise require a finite
                # effective expansion with each row covered; never infer from files.
                proven = False
                for condition in cover:
                    try:
                        if constrain_query(query, condition).to_dict() == q:
                            proven = True
                    except QueryError as exc:
                        if exc.code != "constraint_conflict":
                            raise
                if not proven:
                    rows = expand_queries(
                        [query],
                        max_expansion=configuration.execution_defaults["max_expansion"],
                    )
                    proven = all(any(matches(row, c) for c in cover) for row in rows)
                if not proven:
                    raise QueryError(
                        "unsupported",
                        "/queries",
                        "mapping predicates do not cover the requested conditions",
                        {"reason": "mapping_coverage_gap", "query_index": qi},
                    )
            else:
                branches = [
                    dict(
                        index=0,
                        backend="grib2",
                        scope={},
                        candidate_filter=q.get("native", {}).get("grib", {}),
                        residual=q,
                        basis=[
                            dict(
                                kind="builtin",
                                responsibility="vertical",
                                rule="grib.fixed_surfaces",
                            ),
                            dict(
                                kind="builtin", responsibility="time", rule="grib.time"
                            ),
                        ],
                    )
                ]
            translations.append(
                dict(
                    query_index=qi,
                    coverage=dict(
                        status="passed",
                        message="Exhaustive explicit-file acquisition with exact returned Query verification",
                    ),
                    branches=branches,
                    checks=[
                        dict(
                            code="context_resolved",
                            status="passed",
                            message="Explicit configuration frozen; no product identity inferred",
                        ),
                        dict(
                            code="complete_retrieval_supported",
                            status="passed",
                            message="Full local message iteration without persistent indexes",
                        ),
                        dict(
                            code="return_metadata_sufficient",
                            status="pending",
                            message="Native template and metadata are checked during acquisition",
                        ),
                    ],
                )
            )
        expected = (
            expected_from_domain(
                queries,
                self.expected_domain,
                configuration,
                identity_fields=self.identity_fields,
            )
            if self.expected_domain is not None
            else tuple(None for _ in queries)
        )
        return Plan(tuple(translations), expected)

    def start(self, plan):
        return GribScan(self, plan)

    def close(self):
        pass  # Per-execution file handles and per-load message handles are scoped.

    def mapping(self, branch):
        basis = next((b for b in branch["basis"] if b["kind"] == "mapping"), None)
        if basis is None:
            return None
        resource = next(
            r
            for r in self.configuration.resources.mappings
            if r["id"] == basis["resource"]["id"]
        )
        return next(m for m in resource["mappings"] if m["id"] == basis["mapping"])


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
            "adapter": software_origin("grib.standard-finite-v1"),
            "native_library": "eccodes=" + eccodes.codes_get_api_version(),
        }
        self._iterator = None
        self.checks = {}

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
                        metadata = _metadata(header.handle)
                        # Gather only finite raw candidates; known absent native
                        # predicates are ordinary non-matches, not unknown keys.
                        selected = [
                            (qi, b)
                            for qi, b in branches
                            if native_matches(metadata, b["candidate_filter"])
                            and native_matches(
                                metadata,
                                b["residual"].get("native", {}).get("grib", {}),
                            )
                        ]
                        if not selected:
                            continue
                        grib.applicability(metadata)
                        vertical = grib.fixed_surfaces(
                            metadata,
                            vertical_definition=self.backend.vertical_definition,
                        )
                        times, interval = grib.time_fields(metadata)
                        members = (
                            {}
                            if self.backend.numbering is None
                            and all(
                                self.backend.mapping(b) is None for _, b in selected
                            )
                            else grib.member(
                                metadata,
                                self.backend.configuration,
                                numbering=self.backend.numbering,
                            )
                        )
                        base = {**vertical, **times, **members}
                        interpretations = []
                        for qi, branch in selected:
                            mapping = self.backend.mapping(branch)
                            if (
                                mapping is not None
                                and "time" in mapping["applies_to"]
                                and not matches(
                                    base, {"time": thaw(mapping["applies_to"]["time"])}
                                )
                            ):
                                continue
                            if mapping is not None and not matches(
                                base,
                                {
                                    k: v
                                    for k, v in mapping["when"].items()
                                    if k != "parameter"
                                },
                            ):
                                continue
                            identity, meta = self._interpret(
                                base, metadata, mapping, interval
                            )
                            matching = next(
                                (
                                    item
                                    for item in interpretations
                                    if item[0] == identity and item[1] == meta
                                ),
                                None,
                            )
                            if matching is not None:
                                matching[2].append((qi, branch["index"]))
                            else:
                                interpretations.append(
                                    [identity, meta, [(qi, branch["index"])]]
                                )
                        if len(interpretations) > 1:
                            raise QueryError(
                                "invalid_config",
                                "/mappings",
                                "one native record has conflicting active interpretations",
                                {"reason": "ambiguous_mapping"},
                            )
                        if not interpretations:
                            continue
                        identity, meta, links = interpretations[0]
                        grid, lat, lon, shape = _grid(header.handle)
                        offset = header.offset
                        meta.update(
                            source={
                                "path": str(snapshot.path),
                                "offset": offset,
                                "fingerprint": list(snapshot.fingerprint),
                            },
                            native_fields={
                                k: v for k, v in metadata.items() if v is not None
                            },
                        )
                        for qi, _ in links:
                            self.checks[qi] = [
                                dict(
                                    code="return_metadata_sufficient",
                                    status="passed",
                                    message="All acquired target candidates used for interpretation were verified",
                                )
                            ]
                        yield FieldReference(
                            repr((snapshot.fingerprint, offset)),
                            Query(identity),
                            meta,
                            grid,
                            lambda s=snapshot, o=offset, la=lat, lo=lon, sh=shape: (
                                _load(s, o, la, lo, sh)
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

    def _interpret(self, base, native, mapping, interval):
        if mapping is None:
            unit = native.get("units")
            unit = None if unit in {None, "", "unknown", "~"} else unit
            return {
                **base,
                "native": {"grib": {k: v for k, v in native.items() if v is not None}},
            }, dict(
                source_unit=unit,
                unit=unit,
                vertical_definition=self.backend.vertical_definition
                or {"id": "WMO.GRIB2.fixed-surfaces"},
            )
        parameter = self.backend.configuration.resources.parameter(
            mapping["parameter_id"]
        )
        fixed = parameter["fixed_conditions"]
        if not matches(base, {k: v for k, v in fixed.items() if k != "statistics"}):
            metadata_error(
                "fixed_definition_mismatch",
                "native field violates its mapped fixed definition",
            )
        unit_rule = (
            mapping["native"]
            .get("translate", {})
            .get("unit", {"rule": "common.value_unit"})
        )
        probability = native["productDefinitionTemplateNumber"] in {5, 9}
        object_unit = native.get("parameterUnits") if probability else None
        # ecCodes parameterUnits uses this SI spelling while units uses m s**-1.
        # This finite spelling equivalence does not infer a parameter identity.
        object_unit = {"m s-1": "m/s"}.get(object_unit, object_unit)
        if probability and not unit_rule.get("config", {}).get("source_unit"):
            raise QueryError(
                "invalid_config",
                "/mappings/native/translate/unit",
                "probability field value unit needs explicit encoding evidence",
                {"reason": "missing_context"},
            )
        if probability and object_unit in {None, "", "unknown", "~"}:
            metadata_error(
                "missing_native_metadata",
                "probability threshold has no native parameter unit",
                missing_fields=["parameterUnits"],
            )
        stats = grib.statistics(
            native,
            fixed,
            base,
            interval,
            resources=self.backend.configuration.resources,
            product=self.backend.configuration.product,
            object_unit=object_unit,
        )
        requirement = value_unit(
            # Probability template parameter units describe the event object;
            # its packed field scale is a separate, explicitly declared fact.
            None if probability else native.get("units"),
            parameter["unit"],
            thaw(unit_rule),
            quantity_kind=self.backend.quantity_kinds.get(parameter["parameter_id"]),
        )
        return {
            **base,
            "parameter": parameter["parameter_id"],
            "native": {"grib": {k: v for k, v in native.items() if v is not None}},
        }, dict(
            parameter_id=parameter["parameter_id"],
            parameter_name=parameter["name"],
            fixed_conditions=thaw(fixed),
            source_unit=requirement.source,
            unit=parameter["unit"],
            statistics=stats,
            **(
                {
                    "probability_unit_basis": {
                        "threshold_unit": object_unit,
                        "threshold_origin": "native.parameterUnits",
                        "field_unit": requirement.source,
                        "field_origin": "mapping.common.value_unit.source_unit",
                    }
                }
                if probability
                else {}
            ),
            vertical_definition=self.backend.vertical_definition
            or {"id": "WMO.GRIB2.fixed-surfaces"},
            **(
                {"description": parameter["description"]}
                if "description" in parameter
                else {}
            ),
            **(
                {
                    "quantity_kind": self.backend.quantity_kinds[
                        parameter["parameter_id"]
                    ]
                }
                if parameter["parameter_id"] in self.backend.quantity_kinds
                else {}
            ),
        )


def _grid(handle):
    import eccodes

    if (
        eccodes.codes_get_string(handle, "gridType") != "regular_ll"
        or eccodes.codes_get_long(handle, "jPointsAreConsecutive")
        or eccodes.codes_get_long(handle, "alternativeRowScanning")
    ):
        metadata_error(
            "unsupported_native_encoding",
            "grid/scanning form needs a separately validated adapter",
        )
    ni, nj = eccodes.codes_get_long(handle, "Ni"), eccodes.codes_get_long(handle, "Nj")
    lat = eccodes.codes_get_double_array(handle, "latitudes").reshape(nj, ni)
    lon = eccodes.codes_get_double_array(handle, "longitudes").reshape(nj, ni)
    if not np.all(lat == lat[:, 0, None]) or not np.all(lon == lon[0, None, :]):
        metadata_error(
            "unsupported_native_encoding",
            "grid does not have independent regular latitude/longitude axes",
        )
    grid = {
        "type": "regular_ll",
        "definition": eccodes.codes_get_string(handle, "md5GridSection"),
        "Ni": ni,
        "Nj": nj,
    }
    return grid, lat[:, 0].copy(), lon[0].copy(), (nj, ni)


def _load(snapshot, offset, lat, lon, shape):
    import eccodes
    from reki.grib_io import load_message_at_offset

    def decode():
        handle = load_message_at_offset(snapshot.path, offset)
        if handle is None:
            raise SourceError(
                "decode_failed", "", "record offset no longer identifies a message"
            )
        try:
            record_io_event("value_decode_count")
            values = eccodes.codes_get_double_array(handle, "values").reshape(shape)
            if eccodes.codes_get_long(handle, "bitmapPresent"):
                bitmap = eccodes.codes_get_long_array(handle, "bitmap").reshape(shape)
                values = np.where(bitmap, values, np.nan)
            return xr.DataArray(
                values,
                dims=("latitude", "longitude"),
                coords={"latitude": lat, "longitude": lon},
            )
        except eccodes.CodesInternalError as exc:
            raise SourceError(
                "decode_failed", "", "ecCodes value decoding failed"
            ) from exc
        finally:
            eccodes.codes_release(handle)

    return snapshot.load(decode)
