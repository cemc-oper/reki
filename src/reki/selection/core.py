"""Selection, presence reports and ownership, independent of native backends."""

import json
from pathlib import Path

from cedarkit_query import (
    Query,
    QueryError,
    SourceError,
    CompletenessError,
    QueryExplanation,
    QueryReport,
    combine_queries,
    constrain_query,
    expand_queries,
    intersect_queries,
    normalize_query,
    prepare_queries,
)
from reki.catalog import plan_source_binding
from reki.catalog.model import thaw
from .backend import Plan, UnavailableBackend, plan_dict, is_concrete


def key(value):
    return json.dumps(thaw(value), sort_keys=True, separators=(",", ":"))


def matches(identity, query):
    """Check the complete Query, even when a candidate filter/residual is empty."""
    identity = normalize_query(identity).to_dict()
    raw = Query(query).to_dict()
    if (
        "level_type" not in raw
        and "level_type" in identity
        and _needs_vertical_type(raw)
    ):
        raw = constrain_query(raw, {"level_type": identity["level_type"]}).to_dict()
    query = normalize_query(raw).to_dict()
    for name, value in query.items():
        if name not in identity:
            return False
        if name == "native":
            for backend, conditions in value.items():
                if not set(conditions) <= set(identity[name].get(backend, {})):
                    return False
    return intersect_queries(identity, query) is not None


def _policy(value, default):
    value = default if value is None else value
    if value not in ("available", "required"):
        raise QueryError(
            "invalid_config", "/completeness", "invalid completeness policy"
        )
    return value


def _check_paths(configuration):
    source = configuration.source
    for name in ("path", "directory", "root", "config"):
        if name not in source:
            continue
        paths = source[name] if isinstance(source[name], tuple) else (source[name],)
        for path in paths:
            p = Path(path)
            try:
                is_dir = name in {"root", "directory"}
                if not p.exists():
                    raise SourceError(
                        "resource_not_found",
                        "/source/" + name,
                        "configured path does not exist",
                    )
                if (is_dir and not p.is_dir()) or (not is_dir and not p.is_file()):
                    raise QueryError(
                        "invalid_config",
                        "/source/" + name,
                        "configured path has the wrong kind",
                    )
            except PermissionError as exc:
                raise SourceError(
                    "permission_denied",
                    "/source/" + name,
                    "cannot inspect configured path",
                ) from exc


def _validated_plan(plan, branches, context):
    if not isinstance(plan, Plan) or len(plan.expected) != len(branches):
        raise QueryError("invalid_config", "", "invalid backend plan")
    if [t["query_index"] for t in plan.translations] != list(range(len(branches))):
        raise QueryError(
            "invalid_config", "", "backend translations must follow query index order"
        )
    # Use QueryReport for structural/link validation without fabricating origins steps.
    empty = dict(
        status="unchecked",
        expected_count=None,
        satisfied_count=None,
        field_count=0,
        missing=[],
        reasons=[],
    )
    translations = plan_dict(plan)
    for t in translations:
        for b in t["branches"]:
            b["execution"] = {"status": "not_started", "reason": "first_match_selected"}
    QueryReport(
        {
            "schema_version": 1,
            "completeness": "available",
            "context": context,
            "overall": empty
            if branches
            else dict(empty, status="complete", expected_count=0, satisfied_count=0),
            "queries": [dict(b, summary=empty) for b in branches],
            "translations": translations,
        }
    )
    expected = []
    for branch, rows in zip(branches, plan.expected):
        if rows is None:
            expected.append(None)
            continue
        unique = {}
        for row in rows:
            normalized = normalize_query(thaw(row))
            expanded = expand_queries([normalized])
            if len(expanded) != 1 or not is_concrete(normalized.to_dict()):
                raise QueryError(
                    "invalid_config", "", "expected identities must be concrete"
                )
            if not matches(normalized, branch["query"]):
                raise QueryError(
                    "invalid_config", "", "expected identity exceeds effective Query"
                )
            unique[key(normalized.to_dict())] = normalized.to_dict()
        expected.append(tuple(unique.values()))
    return Plan(tuple(plan_dict(plan)), tuple(expected))


class QuerySource:
    """Own configuration and backend resources, never executed Query results."""

    def __init__(self, configuration, backend=None):
        self._configuration = configuration
        self._backend = UnavailableBackend() if backend is None else backend
        self._closed = False

    @property
    def configuration(self):
        return self._configuration

    def _ensure_open(self):
        if self._closed:
            raise SourceError(
                "io_error", "", "source is closed", {"operation": "selection"}
            )

    def close(self):
        if not self._closed:
            self._closed = True
            self._backend.close()

    def __enter__(self):
        self._ensure_open()
        return self

    def __exit__(self, *exc):
        self.close()

    def sel(self, queries=None, **conditions):
        return Selection(self).sel(queries, **conditions)


def from_source(source, *, context=None, client=None):
    """Construct the new Query source without discovery, scans or service calls.

    Business product selection/registered backend factories are supplied by I06,
    using construct_source; no product/version is inferred by this entry point.
    """
    configuration = plan_source_binding(source, context=context, client=client)
    return construct_source(configuration)


def construct_source(configuration, backend=None):
    """Internal I04/I06 integration entry; no public backend injection protocol."""
    _check_paths(configuration)
    return QuerySource(configuration, backend)


class Selection:
    def __init__(self, owner, inputs=(), prepared=(), indexes=()):
        self._owner = owner
        self._inputs = inputs
        self._prepared = prepared
        self._indexes = indexes

    @property
    def _limit(self):
        return self._owner.configuration.execution_defaults["max_expansion"]

    def _branches(self, steps=None):
        result = list(
            combine_queries(
                self._prepared if steps is None else steps, max_expansion=self._limit
            )
        )
        for branch in result:
            origins = {
                (o["step_index"], self._indexes[o["step_index"]][o["query_index"]])
                for o in branch["origins"]
            }
            branch["origins"] = [
                dict(step_index=si, query_index=qi) for si, qi in sorted(origins)
            ]
        return result

    def sel(self, queries=None, **conditions):
        self._owner._ensure_open()
        if queries is not None and conditions:
            raise QueryError(
                "invalid_query", "/queries", "do not mix Query and keyword forms"
            )
        queries = conditions if queries is None else queries
        inputs = list(queries) if isinstance(queries, (list, tuple)) else [queries]
        if not inputs:
            raise QueryError("invalid_query", "/queries", "Query list must be nonempty")
        config = self._owner.configuration
        raw = []
        qi = 0
        try:
            prepared, indexes = [], []
            for qi, value in enumerate(inputs):
                q = value if isinstance(value, Query) else Query(value)
                raw.append(q)
                prepared_input = q
                if (
                    "level_type" not in q.to_dict()
                    and _needs_vertical_type(q.to_dict())
                    and self._prepared
                ):
                    previous = self._branches()
                    # Only a unique already-established type can bind a partial selector.
                    # Do not import prior level values as fixed scope constraints.
                    kinds = {b["query"].get("level_type") for b in previous}
                    if len(kinds) == 1 and None not in kinds:
                        prepared_input = Query(
                            {"level_type": kinds.pop(), **q.to_dict()}
                        )
                if "parameter" in q.to_dict() and config.resources is None:
                    raise QueryError(
                        "invalid_config",
                        "/parameter",
                        "business queries need a parameter registry",
                        {"reason": "missing_context"},
                    )
                values = _prepare_input(prepared_input, config)
                prepared.extend(values)
                indexes.extend([qi] * len(values))
            # Shared expansion applies configured member roles, without guessing applicability.
            for pi, q in enumerate(prepared):
                qi = indexes[pi]
                expand_queries(
                    [q],
                    max_expansion=self._limit,
                    member_roles=thaw(config.member_roles),
                    cemc=config.cemc_member_roles,
                )
            selection = Selection(
                self._owner,
                self._inputs + (tuple(raw),),
                self._prepared + (tuple(prepared),),
                self._indexes + (tuple(indexes),),
            )
            selection._plan(selection._branches())
        except QueryError as exc:
            # Preserve registered classification/count facts and add selection-local origins.
            raise QueryError(
                exc.code,
                exc.path
                if exc.path.startswith("/queries")
                else f"/queries/{qi}" + exc.path,
                exc.message,
                {
                    **thaw(exc.context),
                    "stage": "selection",
                    "origins": [
                        {"step_index": len(self._inputs), "query_index": i}
                        for i in [qi]
                    ],
                },
            ) from exc
        return selection

    def _plan(self, branches):
        if not branches:
            return Plan((), ())
        plan = self._owner._backend.plan(
            tuple(Query(b["query"]) for b in branches), self._owner.configuration
        )
        return _validated_plan(
            plan, branches, self._owner.configuration.report_context()
        )

    def explain(self):
        branches = self._branches()
        plan = self._plan(branches)
        steps = []
        previous = []
        for si, inputs in enumerate(self._inputs):
            current = self._branches(self._prepared[: si + 1])
            origins = [{"step_index": si, "query_index": i} for i in range(len(inputs))]
            changes = []
            normalized = []
            for qi, q in enumerate(inputs):
                data = q.to_dict()
                kinds = {
                    p.to_dict().get("level_type")
                    for p, origin in zip(self._prepared[si], self._indexes[si])
                    if origin == qi
                }
                if (
                    "level_type" not in data
                    and _needs_vertical_type(data)
                    and len(kinds) == 1
                    and None not in kinds
                ):
                    data = {"level_type": kinds.pop(), **data}
                normalized.append(normalize_query(data).to_dict())
            if [q.to_dict() for q in inputs] != normalized:
                changes.append(
                    dict(
                        code="normalized",
                        origins=origins,
                        message="Canonicalized units, selectors and time relationships",
                    )
                )
            if any(
                "valid_time" not in q.to_dict() and "valid_time" in n
                for q, n in zip(inputs, normalized)
            ):
                changes.append(
                    dict(
                        code="derived",
                        origins=origins,
                        message="Derived valid time from reference time and step",
                    )
                )
            if normalized != [q.to_dict() for q in self._prepared[si]]:
                changes.append(
                    dict(
                        code="constrained",
                        origins=origins,
                        message="Applied parameter identity, fixed definitions and source scope",
                    )
                )
            if si and current != previous:
                changes.append(
                    dict(
                        code="narrowed" if current else "pruned",
                        origins=origins,
                        message="Intersected this step with previous selection branches",
                    )
                )
            surviving = {
                (o["step_index"], o["query_index"])
                for b in current
                for o in b["origins"]
            }
            removed = [
                o
                for o in origins + [o for b in previous for o in b["origins"]]
                if (o["step_index"], o["query_index"]) not in surviving
            ]
            if removed and current:
                unique = {(o["step_index"], o["query_index"]) for o in removed}
                changes.append(
                    dict(
                        code="pruned",
                        origins=[
                            dict(step_index=s, query_index=q) for s, q in sorted(unique)
                        ],
                        message="Removed disjoint input branches",
                    )
                )
            if any(
                len({o["query_index"] for o in b["origins"] if o["step_index"] == si})
                > 1
                for b in current
            ):
                changes.append(
                    dict(
                        code="merged",
                        origins=origins,
                        message="Merged equivalent branches and retained contributing origins",
                    )
                )
            steps.append(
                dict(
                    index=si,
                    input_queries=[q.to_dict() for q in inputs],
                    effective_queries=current,
                    changes=changes,
                )
            )
            previous = current
        expanded = expand_queries(
            [b["query"] for b in branches], max_expansion=self._limit
        )
        continuous = any(_has_continuous(b["query"]) for b in branches)
        known = all(rows is not None for rows in plan.expected)
        count = (
            len({key(row) for rows in plan.expected for row in rows}) if known else None
        )
        return QueryExplanation(
            dict(
                effective_queries=branches,
                context=self._owner.configuration.report_context(),
                steps=steps,
                analysis=dict(
                    expansion_count=None if continuous else len(expanded),
                    expected_count=count,
                    checks=[],
                    translations=plan_dict(plan),
                ),
            )
        )

    def _execute(self, operation, completeness):
        self._owner._ensure_open()
        policy = _policy(
            completeness, self._owner.configuration.execution_defaults["completeness"]
        )
        branches = self._branches()
        plan = self._plan(branches)
        refs, seen, visited, matched_queries = [], {}, set(), {}
        exhausted = True
        context = self._owner.configuration.report_context()
        if branches:
            scan = self._owner._backend.start(plan)
            try:
                plan = _validated_plan(scan.plan, branches, context)
                if any(t["coverage"]["status"] != "passed" for t in plan.translations):
                    raise QueryError(
                        "unsupported",
                        "/queries",
                        "candidate coverage remains pending",
                        {"stage": "selection", "reason": "translation_unavailable"},
                    )
                context = _execution_context(context, thaw(scan.context))
                for ref in scan:
                    _validate_reference(ref, self._owner.configuration)
                    for qi, bi in ref.branches:
                        if not 0 <= qi < len(branches) or not 0 <= bi < len(
                            plan.translations[qi]["branches"]
                        ):
                            raise QueryError(
                                "invalid_config", "", "invalid backend branch reference"
                            )
                        visited.add((qi, bi))
                    if not ref.branches:
                        raise QueryError(
                            "invalid_config", "", "candidate lacks branch references"
                        )
                    # Candidate and residual cannot replace full Query verification.
                    selected = set()
                    for qi, bi in ref.branches:
                        residual = thaw(
                            plan.translations[qi]["branches"][bi]["residual"]
                        )
                        statistics = residual.pop("statistics", None)
                        if (
                            matches(ref.identity, branches[qi]["query"])
                            and matches(ref.identity, residual)
                            and (
                                statistics is None
                                or thaw(ref.metadata.get("statistics")) == statistics
                            )
                        ):
                            selected.add(qi)
                    if not selected:
                        continue
                    matched_queries.setdefault(ref.record_id, set()).update(selected)
                    if ref.record_id in seen:
                        old = seen[ref.record_id]
                        if (
                            old.identity != ref.identity
                            or old.grid != ref.grid
                            or old.metadata != ref.metadata
                        ):
                            raise SourceError(
                                "metadata_interpretation_failed",
                                "",
                                "record reference changed",
                                {"reason": "inconsistent_native_metadata"},
                            )
                        continue
                    seen[ref.record_id] = ref
                    refs.append(ref)
                    if operation == "one" and policy == "available" and len(refs) == 2:
                        raise QueryError(
                            "multiple_matches",
                            "/queries",
                            "one found multiple actual fields",
                            {
                                "operation": "one",
                                "stage": "selection",
                                "count_lower_bound": 2,
                            },
                        )
                    if operation == "first" and policy == "available":
                        exhausted = False
                        break
            finally:
                scan.close()
        translations = plan_dict(plan)
        for t in translations:
            for b in t["branches"]:
                b["execution"] = (
                    {"status": "exhausted"}
                    if exhausted
                    else {
                        "status": "stopped_early"
                        if (t["query_index"], b["index"]) in visited
                        else "not_started",
                        "reason": "first_match_selected",
                    }
                )
        report = _report(
            branches,
            plan,
            refs,
            policy,
            context,
            translations,
            exhausted,
            matched_queries,
        )
        if policy == "required" and report.overall["status"] != "complete":
            code = (
                "missing_fields"
                if report.overall["status"] == "missing"
                else "completeness_undetermined"
            )
            raise CompletenessError(
                code,
                "/queries",
                report=report,
                context={"operation": operation, "stage": "completeness"},
            )
        fields = tuple(Field(self._owner, ref, report) for ref in refs)
        if operation == "first":
            return fields[0] if fields else None
        if operation == "one":
            if len(fields) != 1:
                raise QueryError(
                    "no_match" if not fields else "multiple_matches",
                    "/queries",
                    "one requires exactly one actual field",
                    {"operation": "one", "stage": "selection", "count": len(fields)},
                )
            return fields[0]
        return Fields(self._owner, fields, report)

    def first(self, *, completeness=None):
        return self._execute("first", completeness)

    def one(self, *, completeness=None):
        return self._execute("one", completeness)

    def all(self, *, completeness=None):
        return self._execute("all", completeness)

    def to_xarray(self, *, completeness=None, rename=None):
        return self.all(completeness=completeness).to_xarray(rename=rename)


def _report(
    branches, plan, refs, policy, context, translations, exhausted, matched_queries
):
    summaries, missing_all, reasons_all = [], {}, []
    expected_all, satisfied_all = set(), set()
    unknown = False
    for b, expected in zip(branches, plan.expected):
        qi = b["index"]
        actual = [r for r in refs if qi in matched_queries[r.record_id]]
        missing, reasons = [], []
        if expected is None:
            unknown = True
            reasons.append(
                dict(
                    code="expected_set_unknown",
                    message="No complete expected identity set is defined",
                    query_indexes=[qi],
                )
            )
            ec = sc = None
        else:
            ec = len(expected)
            satisfied = {
                key(row)
                for row in expected
                if any(matches(r.identity, thaw(row)) for r in actual)
            }
            sc = len(satisfied)
            expected_all.update(key(row) for row in expected)
            satisfied_all.update(satisfied)
            if exhausted:
                for row in expected:
                    if key(row) not in satisfied:
                        entry = dict(selection=thaw(row), query_indexes=[qi])
                        missing.append(entry)
                        item = missing_all.setdefault(
                            key(row), dict(selection=thaw(row), query_indexes=[])
                        )
                        item["query_indexes"].append(qi)
        if not exhausted:
            reasons.append(
                dict(
                    code="selection_not_exhausted",
                    message="first stopped before candidate exhaustion",
                    query_indexes=[qi],
                )
            )
        status = "missing" if missing else "unchecked" if reasons else "complete"
        summary = dict(
            status=status,
            expected_count=ec,
            satisfied_count=sc,
            field_count=len(actual),
            missing=missing,
            reasons=reasons,
        )
        summaries.append(dict(b, summary=summary))
        reasons_all.extend(reasons)
    status = "missing" if missing_all else "unchecked" if reasons_all else "complete"
    overall = dict(
        status=status,
        expected_count=None if unknown else len(expected_all),
        satisfied_count=None if unknown else len(satisfied_all),
        field_count=len(refs),
        missing=list(missing_all.values()),
        reasons=reasons_all,
    )
    return QueryReport(
        dict(
            schema_version=1,
            completeness=policy,
            context=context,
            overall=overall,
            queries=summaries,
            translations=translations,
        )
    )


class Field:
    def __init__(self, owner, reference, report):
        self._owner, self._reference, self._report = owner, reference, report

    @property
    def identity(self):
        return self._reference.identity

    @property
    def metadata(self):
        return self._reference.metadata

    @property
    def report(self):
        return self._report

    def to_xarray(self, *, rename=None):
        return Fields(self._owner, (self,), self.report).to_xarray(rename=rename)


class Fields:
    def __init__(self, owner, fields, report):
        self._owner, self._fields, self._report = owner, tuple(fields), report

    @property
    def report(self):
        return self._report

    def __len__(self):
        return len(self._fields)

    def __iter__(self):
        return iter(self._fields)

    def __getitem__(self, index):
        return self._fields[index]

    def first(self):
        return self._fields[0] if self._fields else None

    def to_xarray(self, *, rename=None):
        self._owner._ensure_open()
        from .output import assemble

        return assemble(self._fields, self.report, rename, self._owner.configuration)


def _has_continuous(value):
    if isinstance(value, dict):
        return ("range" in value and "every" not in value["range"]) or any(
            _has_continuous(v) for v in value.values()
        )
    if isinstance(value, (list, tuple)):
        return any(_has_continuous(v) for v in value)
    return False


def _needs_vertical_type(query):
    layer = query.get("layer", ())
    layers = layer if isinstance(layer, (list, tuple)) else [layer]
    return "level" in query or any(
        isinstance(endpoint, (int, float))
        for item in layers
        for endpoint in item.values()
    )


def _prepare_input(query, configuration):
    scope = configuration.scope.to_dict()
    resources = configuration.resources
    if "level_type" not in scope and _needs_vertical_type(scope):
        preliminary = (
            prepare_queries([query], resources)
            if resources is not None
            else (normalize_query(query),)
        )
        result = []
        for value in preliminary:
            kind = value.to_dict().get("level_type")
            if kind is None:
                raise QueryError(
                    "invalid_config",
                    "/context/scope/level_type",
                    "vertical scope needs an explicit effective type",
                    {"reason": "missing_context"},
                )
            bound = {"level_type": kind, **scope}
            result.extend(
                prepare_queries([value], resources, scope=bound)
                if resources is not None
                else (constrain_query(value, bound),)
            )
        return tuple(result)
    return (
        prepare_queries([query], resources, scope=scope)
        if resources is not None
        else (constrain_query(query, scope),)
    )


def _validate_reference(ref, configuration):
    identity = ref.identity.to_dict()
    if "parameter" in identity and configuration.resources is None:
        raise QueryError(
            "invalid_config",
            "/context/parameter_registry",
            "canonical field needs its parameter registry",
            {"reason": "missing_context"},
        )
    if not matches(identity, configuration.scope):
        raise SourceError(
            "metadata_interpretation_failed",
            "",
            "field violates source scope",
            {"reason": "fixed_definition_mismatch"},
        )
    if "member" in identity:
        role = configuration.member_role(identity["member"])
        if role is not None and identity.get("member_role") != role:
            raise SourceError(
                "metadata_interpretation_failed",
                "",
                "member role differs from effective configuration",
                {"reason": "invalid_member_metadata"},
            )
    if configuration.resources is not None and "parameter" in identity:
        p = configuration.resources.parameter(identity["parameter"])
        fixed = p.get("fixed_conditions", {})
        constraints = {k: v for k, v in fixed.items() if k != "statistics"}
        metadata = thaw(ref.metadata)
        if (
            not matches(identity, constraints)
            or metadata.get("parameter_id") != p["parameter_id"]
            or metadata.get("parameter_name") != p["name"]
            or metadata.get("unit") != p["unit"]
            or metadata.get("fixed_conditions", {}) != fixed
            or (
                "statistics" in fixed
                and metadata.get("statistics") != fixed["statistics"]
            )
        ):
            raise SourceError(
                "metadata_interpretation_failed",
                "",
                "canonical metadata differs from loaded definition",
                {"reason": "fixed_definition_mismatch"},
            )


def _execution_context(context, extra):
    # Acquired source facts may augment configuration, never overwrite definitions,
    # scopes, versions, defaults or resource origins. No config/client/request body.
    if set(extra) - {"source"} or set(extra.get("source", {})) - {
        "paths",
        "fingerprints",
        "version",
    }:
        raise QueryError(
            "invalid_config", "", "backend returned unsupported report context"
        )
    return {
        **context,
        "source": {**context.get("source", {}), **extra.get("source", {})},
    }
