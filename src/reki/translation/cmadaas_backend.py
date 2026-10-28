"""Controlled single-grid backend boundary; no production MUSIC registration.

The transport supplies the exact response wrapper defined by InterfaceContract.
A real nuwe-cmadaas transport/contract needs independent association and complete
retrieval evidence before registration. No attrs-based request reconstruction.
"""

import hashlib
import json
from collections import defaultdict

from cedarkit_query import (
    QueryError,
    SourceError,
    Query,
    expand_queries,
    validate_rule,
    constrain_query,
    normalize_statistics,
)
from reki.catalog.model import thaw, freeze
from reki.selection.backend import Plan, FieldReference, BranchEvent, is_concrete
from reki.selection.core import expected_from_domain, matches
from . import cmadaas
from .common import unsupported, metadata_error, value_unit, software_origin


def _key(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class CmadaasBackend:
    def __init__(
        self,
        configuration,
        contract,
        transport,
        *,
        owns_transport=False,
        expected_domain=None,
        identity_fields=(),
        quantity_kinds=None,
    ):
        binding = configuration.source_binding
        if binding is None or thaw(binding["interface_contract"]) != contract.reference:
            raise QueryError(
                "invalid_config",
                "/source/interface_contract",
                "source does not reference this exact internal contract",
                {"reason": "missing_context"},
            )
        if contract.level_key_kind != "level_type_and_level":
            unsupported("this transport slice requires the complete joint level key")
        self.configuration, self.contract, self.transport = (
            configuration,
            contract,
            transport,
        )
        self.owns_transport = owns_transport
        self.expected_domain, self.identity_fields = (
            freeze(expected_domain),
            tuple(identity_fields),
        )
        self.quantity_kinds = freeze(quantity_kinds or {})
        self._closed = False

    def close(self):
        if not self._closed:
            self._closed = True
            if self.owns_transport:
                self.transport.close()

    def plan(self, queries, configuration):
        translations = []
        binding = configuration.source_binding
        for qi, query in enumerate(queries):
            q = query.to_dict()
            if "native" in q:
                unsupported(
                    "GRIB native selectors do not apply to a CMADaaS contract",
                    query_index=qi,
                )
            if not isinstance(q.get("parameter"), str):
                unsupported(
                    "this single-grid contract requires an exact parameter",
                    query_index=qi,
                )
            candidates = []
            for resource in configuration.resources.mappings:
                if resource["backend"] != "cmadaas":
                    continue
                for mapping in resource["mappings"]:
                    if mapping["parameter_id"] != q["parameter"]:
                        continue
                    scope = thaw(mapping["applies_to"])
                    known = configuration.report_context()["source"]
                    from cedarkit_query.normalize import _contains

                    if any(
                        k not in known or not _contains(v, known[k], "literal")
                        for k, v in scope.items()
                        if k != "time"
                    ):
                        continue
                    try:
                        if constrain_query(query, thaw(mapping["when"])).to_dict() != q:
                            continue
                        if (
                            "time" in scope
                            and constrain_query(
                                query, {"time": scope["time"]}
                            ).to_dict()
                            != q
                        ):
                            continue
                    except QueryError as exc:
                        if exc.code != "constraint_conflict":
                            raise
                        continue
                    candidates.append((resource, mapping))
            if len(candidates) != 1:
                raise QueryError(
                    "invalid_config" if candidates else "unsupported",
                    "/mappings",
                    "single-grid mapping is absent or ambiguous",
                    {
                        "reason": "ambiguous_mapping"
                        if candidates
                        else "mapping_coverage_gap",
                        "query_index": qi,
                    },
                )
            resource, mapping = candidates[0]
            rules = mapping["native"].get("translate", {})
            for duty, rule in rules.items():
                validate_rule(rule, backend="cmadaas", responsibility=duty)
            vertical = rules.get("vertical")
            if vertical is None:
                unsupported("single-grid layer translation requires its exact table")
            table = next(
                t for t in resource["tables"] if t["id"] == vertical["config"]["table"]
            )
            known = configuration.report_context()["source"]
            if any(
                k not in known or not _contains(v, known[k], "literal")
                for k, v in table["applies_to"].items()
                if k != "time"
            ):
                raise QueryError(
                    "invalid_config",
                    "/tables",
                    "table is outside the selected product context",
                    {"reason": "rule_not_applicable"},
                )
            if "time" in table["applies_to"]:
                try:
                    if (
                        constrain_query(
                            query, {"time": thaw(table["applies_to"]["time"])}
                        ).to_dict()
                        != q
                    ):
                        unsupported(
                            "table time domain does not cover the requested query"
                        )
                except QueryError as exc:
                    if exc.code != "constraint_conflict":
                        raise
                    raise QueryError(
                        "unsupported",
                        "/queries",
                        "table time domain does not cover the query",
                        {"reason": "mapping_coverage_gap"},
                    ) from exc
            p = configuration.resources.parameter(q["parameter"])
            if "statistics" not in p["fixed_conditions"]:
                raise QueryError(
                    "invalid_config",
                    "/statistics",
                    "single-grid product statistic needs an effective definition",
                    {"reason": "missing_context"},
                )
            stats = normalize_statistics(
                thaw(p["fixed_conditions"]["statistics"]), complete=True
            )
            if stats["over"] != "time":
                unsupported(
                    "this service slice does not yet interpret ensemble statistical products",
                    query_index=qi,
                )
            rows = expand_queries(
                [query], max_expansion=configuration.execution_defaults["max_expansion"]
            )
            branches = []
            for row in rows:
                data = row.to_dict()
                if (
                    not is_concrete(data)
                    or "level_type" not in data
                    and "layer" not in data
                    or (
                        data.get("level_type")
                        in {
                            "pressure",
                            "height_above_ground",
                            "height_above_sea",
                            "depth_below_land",
                            "model_level",
                        }
                        and "level" not in data
                    )
                ):
                    raise QueryError(
                        "unsupported",
                        "/queries",
                        "a layer table is not a complete product enumeration",
                        {"reason": "unsafe_candidate_expansion", "query_index": qi},
                    )
                if "member" in self.contract.request_roles and "member" not in data:
                    raise QueryError(
                        "unsupported",
                        "/queries",
                        "member enumeration requires an independent finite domain",
                        {"reason": "unsafe_candidate_expansion", "query_index": qi},
                    )
                times = cmadaas.encode_time(row, binding.get("time_zone"))
                layer_rows = cmadaas.vertical_candidates(row, table)
                if not layer_rows:
                    raise QueryError(
                        "unsupported",
                        "/queries",
                        "vertical table does not cover the requested layer",
                        {"reason": "mapping_coverage_gap", "query_index": qi},
                    )
                for layer in layer_rows:
                    native = thaw(mapping["native"]["match"])
                    if (
                        set(native) != {"dataCode", "fcstEle"}
                        or native["dataCode"] != binding["data_code"]
                        or any(not isinstance(v, str) for v in native.values())
                    ):
                        raise QueryError(
                            "invalid_config",
                            "/mappings",
                            "single-grid identity needs exact dataCode and fcstEle",
                            {"reason": "missing_context"},
                        )
                    logical = {**times, **layer["native"]}
                    if "member" in row.to_dict():
                        rule = rules.get("member", {})
                        if rule.get("config", {}).get("table"):
                            members = next(
                                t
                                for t in resource["tables"]
                                if t["id"] == rule["config"]["table"]
                            )
                            codes = [
                                r["native"]["code"]
                                for r in members["rows"]
                                if r["canonical"]["member"] == row.member
                            ]
                            if len(codes) != 1:
                                unsupported(
                                    "this slice requires one service member code per canonical member"
                                )
                            logical["member"] = codes[0]
                        elif self.contract.member_numbering == "canonical":
                            logical["member"] = str(row.member)
                        else:
                            unsupported(
                                "member numbering lacks a registered identity contract"
                            )
                    parameters = dict(native)
                    for role, value in logical.items():
                        field = self.contract.request_roles.get(role)
                        if field is None:
                            if role == "step" and times["step"] == "0":
                                continue
                            unsupported(
                                "requested role is absent from this exact interface contract",
                                role=role,
                            )
                        parameters[field] = value
                    branches.append(
                        dict(
                            index=len(branches),
                            backend="cmadaas",
                            scope={
                                k: thaw(v) for k, v in mapping["applies_to"].items()
                            },
                            candidate_filter=parameters,
                            residual=row.to_dict(),
                            basis=[
                                dict(
                                    kind="mapping",
                                    resource={"kind": "mappings", "id": resource["id"]},
                                    mapping=mapping["id"],
                                ),
                                dict(
                                    kind="mapping",
                                    resource={"kind": "mappings", "id": resource["id"]},
                                    mapping=mapping["id"],
                                    responsibility="vertical",
                                    rule="cmadaas.vertical_table",
                                    table=table["id"],
                                    row=layer["id"],
                                ),
                                dict(
                                    kind="request_association",
                                    contract=self.contract.reference,
                                    fields=["time", "step", "level_type", "level"],
                                ),
                            ],
                        )
                    )
            translations.append(
                dict(
                    query_index=qi,
                    coverage=dict(
                        status="passed",
                        message="Finite paired calls cover the effective discrete query",
                    ),
                    branches=branches,
                    checks=[
                        dict(
                            code="request_association_verified",
                            status="pending",
                            message="Actual response association is checked only during acquisition",
                        ),
                        dict(
                            code="complete_retrieval_supported",
                            status="passed",
                            message="Exact internally registered single-grid contract; no pagination expansion",
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
        return CmadaasScan(self, plan)


class CmadaasScan:
    def __init__(self, backend, plan):
        self.backend, self.plan, self.context = (
            backend,
            plan,
            {
                "origins": {
                    "adapter": software_origin("cmadaas.single-grid-controlled-v1")
                }
            },
        )
        self._iterator = None
        self.records = []  # Acquired response snapshots for this execution, not a source cache.
        self.checks = {}

    def __iter__(self):
        self._iterator = self._fields()
        return self._iterator

    def close(self):
        if self._iterator is not None:
            self._iterator.close()

    def _fields(self):
        backend = self.backend
        groups = defaultdict(list)
        for t in self.plan.translations:
            for branch in t["branches"]:
                groups[_key(thaw(branch["candidate_filter"]))].append(
                    (t["query_index"], branch)
                )
        # Deterministic invocation order is independent of Query input order.
        for request_index, signature in enumerate(sorted(groups)):
            linked = groups[signature]
            parameters = json.loads(signature)
            for qi, b in linked:
                yield BranchEvent(qi, b["index"], "started")
            try:
                response = backend.transport.request(
                    backend.contract.interface_id,
                    backend.contract.method,
                    dict(parameters),
                )
            except TimeoutError as exc:
                raise SourceError(
                    "timeout",
                    "",
                    "service transport timed out",
                    {"request_index": request_index},
                ) from exc
            except PermissionError as exc:
                raise SourceError(
                    "permission_denied",
                    "",
                    "service transport access denied",
                    {"request_index": request_index},
                ) from exc
            except OSError as exc:
                raise SourceError(
                    "io_error",
                    "",
                    "service transport access failed",
                    {"request_index": request_index},
                ) from exc
            record = cmadaas.associate(
                backend.contract, parameters, response, request_index=request_index
            )
            self.records.append(record)
            identities = []
            for qi, branch in linked:
                basis = branch["basis"][0]
                resource = next(
                    r
                    for r in backend.configuration.resources.mappings
                    if r["id"] == basis["resource"]["id"]
                )
                mapping = next(
                    m for m in resource["mappings"] if m["id"] == basis["mapping"]
                )
                tableid = mapping["native"]["translate"]["vertical"]["config"]["table"]
                table = next(t for t in resource["tables"] if t["id"] == tableid)
                vertical, vertical_basis = cmadaas.vertical_table(record, table)
                fixed_step = (
                    backend.configuration.scope.to_dict().get("step")
                    if "step" not in backend.contract.request_roles
                    else None
                )
                times, time_basis = cmadaas.time_fields(
                    record,
                    backend.configuration.source_binding.get("time_zone"),
                    fixed_step=fixed_step,
                )
                rule = mapping["native"]["translate"].get("member", {})
                member_table = next(
                    (
                        t
                        for t in resource["tables"]
                        if t["id"] == rule.get("config", {}).get("table")
                    ),
                    None,
                )
                members, member_basis = cmadaas.member_field(
                    record, backend.configuration, member_table
                )
                identity = {
                    "parameter": mapping["parameter_id"],
                    **vertical,
                    **times,
                    **members,
                }
                parameter = backend.configuration.resources.parameter(
                    mapping["parameter_id"]
                )
                stats, interval, stat_basis = cmadaas.statistics_fields(
                    record, parameter["fixed_conditions"], identity
                )
                fixed = {
                    k: v
                    for k, v in parameter["fixed_conditions"].items()
                    if k != "statistics"
                }
                if not matches(identity, fixed):
                    metadata_error(
                        "fixed_definition_mismatch",
                        "service record violates fixed parameter definition",
                    )
                unit_rule = mapping["native"]["translate"].get(
                    "unit", {"rule": "common.value_unit"}
                )
                requirement = value_unit(
                    response.get("unit"),
                    parameter["unit"],
                    thaw(unit_rule),
                    quantity_kind=backend.quantity_kinds.get(mapping["parameter_id"]),
                )
                meta = dict(
                    parameter_id=parameter["parameter_id"],
                    parameter_name=parameter["name"],
                    unit=parameter["unit"],
                    source_unit=requirement.source,
                    fixed_conditions=thaw(parameter["fixed_conditions"]),
                    statistics=stats,
                    vertical_definition={
                        "table": tableid,
                        "resource": resource["id"],
                        "version": resource["version"],
                    },
                    request_index=request_index,
                    call_record=record,
                    fact_origins={
                        "vertical": vertical_basis,
                        "time": time_basis,
                        "member": member_basis,
                        "statistics": stat_basis,
                    },
                )
                if mapping["parameter_id"] in backend.quantity_kinds:
                    meta["quantity_kind"] = backend.quantity_kinds[
                        mapping["parameter_id"]
                    ]
                identities.append((identity, meta))
            if any(item != identities[0] for item in identities):
                raise QueryError(
                    "invalid_config",
                    "/mappings",
                    "one acquired grid has conflicting interpretations",
                    {"reason": "ambiguous_mapping"},
                )
            array = response.get("data")
            import xarray as xr

            if not isinstance(array, xr.DataArray) or array.ndim != 2:
                metadata_error(
                    "unsupported_native_encoding",
                    "contract response does not contain one two-dimensional grid",
                )
            retained = array.load().copy(
                deep=True
            )  # CMADaaS full-field acquisition exception.
            digest = hashlib.sha256(signature.encode()).hexdigest()
            grid = {
                "contract": backend.contract.reference,
                "shape": list(array.shape),
                "spatial_dimensions": list(array.dims),
            }
            identity, meta = identities[0]
            for qi, _ in linked:
                self.checks[qi] = [
                    dict(
                        code="request_association_verified",
                        status="passed",
                        message="All acquired responses used for interpretation passed exact call association",
                    )
                ]
            yield FieldReference(
                f"service:{id(response)}:{digest}",
                Query(identity),
                meta,
                grid,
                lambda value=retained: value.copy(deep=True),
                tuple((qi, b["index"]) for qi, b in linked),
            )
            for qi, b in linked:
                yield BranchEvent(qi, b["index"], "exhausted")
