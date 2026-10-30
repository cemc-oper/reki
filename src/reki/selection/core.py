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
from cedarkit_query.normalize import _contains, _count
from reki.catalog.model import thaw
from .backend import (
    Plan,
    UnavailableBackend,
    plan_dict,
    is_concrete,
    BranchEvent,
    BranchProgress,
    FieldReference,
)


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
            if name in {"level_type", "level_unit"} and "layer" in identity:
                # A common vertical constraint applies to both layer endpoints.
                # Normalized layers store types/units on those endpoints; the
                # shared intersection below checks compatibility and ordering.
                continue
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


def _selection_error(exc, origins, *, query_index=None):
    path = exc.path
    context = thaw(exc.context)
    query_fields = {
        "parameter",
        "level_type",
        "level",
        "level_unit",
        "layer",
        "time",
        "step",
        "valid_time",
        "member",
        "member_role",
        "native",
    }
    field = path.split("/")[1] if "/" in path else None
    if (
        query_index is not None
        and not context.get("document")
        and not path.startswith(("/context", "/source"))
        and (
            exc.code in {"invalid_query", "constraint_conflict"}
            or field in query_fields
        )
        and not path.startswith("/queries")
    ):
        path = f"/queries/{query_index}" + path
    raise QueryError(
        exc.code,
        path,
        exc.message,
        {**context, "stage": context.get("stage", "selection"), "origins": origins},
    ) from exc


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


def _validated_plan(plan, branches, context, configuration):
    if not isinstance(plan, Plan) or len(plan.expected) != len(branches):
        raise QueryError("invalid_config", "", "invalid backend plan")
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
        if isinstance(t, dict) and isinstance(t.get("branches"), list):
            for b in t["branches"]:
                if isinstance(b, dict):
                    b["execution"] = {
                        "status": "not_started",
                        "reason": "first_match_selected",
                    }
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
    if [t["query_index"] for t in plan.translations] != list(range(len(branches))):
        raise QueryError(
            "invalid_config", "", "backend translations must follow query index order"
        )
    for ti, translation in enumerate(plan.translations):
        for bi, branch in enumerate(translation["branches"]):
            scope = thaw(branch["scope"])
            for name in ("dataset", "product", "product_version"):
                known = context.get("source", {}).get(name)
                values = scope.get(name)
                if known is not None and values is not None:
                    values = values if isinstance(values, list) else [values]
                    if any(v != known for v in values):
                        raise QueryError(
                            "invalid_config",
                            f"/translations/{ti}/branches/{bi}/scope/{name}",
                            "candidate branch contradicts its fixed source identity",
                        )
            if "time" in scope and "time" in context.get("scope", {}):
                try:
                    constrain_query(
                        {"time": scope["time"]}, {"time": context["scope"]["time"]}
                    )
                except QueryError as exc:
                    raise QueryError(
                        "invalid_config",
                        f"/translations/{ti}/branches/{bi}/scope/time",
                        "candidate branch expands its fixed source time scope",
                    ) from exc
    expected = []
    for branch, rows in zip(branches, plan.expected):
        if rows is None:
            expected.append(None)
            continue
        unique = {}
        for ei, row in enumerate(rows):
            try:
                normalized = _expected_identity(thaw(row), configuration)
            except QueryError as exc:
                raise QueryError(
                    "invalid_config", f"/expected/{branch['index']}/{ei}", exc.message
                ) from exc
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


def _check_refinement(previous, current):
    for old, new in zip(previous.expected, current.expected):
        if old is not None and (
            new is None or {key(q) for q in old} != {key(q) for q in new}
        ):
            raise QueryError(
                "invalid_config",
                "",
                "execution cannot replace an already fixed independent expected set",
            )


def _close_scan(iterator, scan, failure):
    cleanup_error = None
    for resource in (iterator, scan) if iterator is not scan else (scan,):
        close = getattr(resource, "close", None)
        if close is not None:
            try:
                close()
            except Exception as exc:
                if cleanup_error is None:
                    cleanup_error = exc
    if cleanup_error is not None:
        if failure is None:
            raise cleanup_error
        failure.add_note(
            "Execution resource cleanup also failed; the original failure is preserved."
        )


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

    Registered builtin datasets carry explicit current-business bindings.
    File discovery and native metadata checks remain terminal operations.
    """
    configuration = plan_source_binding(source, context=context, client=client)
    if configuration.source["kind"] in {"file", "local"}:
        from reki.catalog.current import current_member_numbering
        from reki.translation.grib_backend import GribBackend

        return construct_source(
            configuration,
            GribBackend(
                configuration, numbering=current_member_numbering(configuration)
            ),
        )
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
        raw, prepared, indexes = [], [], []
        si = len(self._inputs)
        for qi, value in enumerate(inputs):
            try:
                q = value if isinstance(value, Query) else Query(value)
                raw.append(q)
                prepared_input = q
                if (
                    "level_type" not in q.to_dict()
                    and _needs_vertical_type(q.to_dict())
                    and self._prepared
                ):
                    kinds = {b["query"].get("level_type") for b in self._branches()}
                    if len(kinds) == 1 and None not in kinds:
                        prepared_input = Query(
                            {"level_type": kinds.pop(), **q.to_dict()}
                        )
                if "parameter" in q.to_dict() and config.resources is None:
                    raise QueryError(
                        "invalid_config",
                        "/context/parameter_registry",
                        "business queries need a parameter registry",
                        {"reason": "missing_context"},
                    )
                values = _prepare_input(prepared_input, config)
                for normalized in values:
                    _check_member_roles(normalized, config)
                prepared.extend(values)
                indexes.extend([qi] * len(values))
            except QueryError as exc:
                _selection_error(
                    exc, [dict(step_index=si, query_index=qi)], query_index=qi
                )
        selection = Selection(
            self._owner,
            self._inputs + (tuple(raw),),
            self._prepared + (tuple(prepared),),
            self._indexes + (tuple(indexes),),
        )
        try:
            branches = selection._branches()
            for branch in branches:
                _check_member_roles(Query(branch["query"]), config)
            expand_queries(
                [b["query"] for b in branches],
                max_expansion=self._limit,
                member_roles=thaw(config.member_roles),
                cemc=config.cemc_member_roles,
            )
        except QueryError as exc:
            origins = {
                (o["step_index"], o["query_index"])
                for b in self._branches()
                for o in b["origins"]
            }
            origins.update((si, i) for i in range(len(raw)))
            _selection_error(
                exc, [dict(step_index=s, query_index=q) for s, q in sorted(origins)]
            )
        # Plan/configuration errors retain their own schema/resource paths. They
        # are not an error in whichever input happened to be processed last.
        selection._plan(branches)
        return selection

    def _plan(self, branches):
        if not branches:
            return Plan((), ())
        try:
            plan = self._owner._backend.plan(
                tuple(Query(b["query"]) for b in branches), self._owner.configuration
            )
            return _validated_plan(
                plan,
                branches,
                self._owner.configuration.report_context(),
                self._owner.configuration,
            )
        except QueryError as exc:
            context = thaw(exc.context)
            index = context.get("query_index")
            involved = (
                [branches[index]]
                if type(index) is int and 0 <= index < len(branches)
                else branches
            )
            origins = {
                (o["step_index"], o["query_index"])
                for b in involved
                for o in b["origins"]
            }
            raise QueryError(
                exc.code,
                exc.path,
                exc.message,
                {
                    **context,
                    "stage": context.get("stage", "selection"),
                    "origins": [
                        dict(step_index=s, query_index=q) for s, q in sorted(origins)
                    ],
                },
            ) from exc

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
                kinds = set()
                for p, origin in zip(self._prepared[si], self._indexes[si]):
                    if origin != qi:
                        continue
                    prepared = p.to_dict()
                    kind = prepared.get("level_type")
                    if kind is None and "layer" in prepared:
                        layers = prepared["layer"]
                        layers = layers if isinstance(layers, list) else [layers]
                        types = {
                            endpoint["type"]
                            for layer in layers
                            for endpoint in layer.values()
                        }
                        if len(types) == 1:
                            kind = types.pop()
                    kinds.add(kind)
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
        refs, seen, matched_queries = [], {}, {}
        execution_checks = {}
        progress = BranchProgress(plan)
        context = self._owner.configuration.report_context()
        if branches:
            scan = self._owner._backend.start(plan)
            iterator, failure = None, None
            try:
                refined = _validated_plan(
                    scan.plan, branches, context, self._owner.configuration
                )
                _check_refinement(plan, refined)
                plan = refined
                progress = BranchProgress(plan)
                if any(t["coverage"]["status"] != "passed" for t in plan.translations):
                    raise QueryError(
                        "unsupported",
                        "/queries",
                        "candidate coverage remains pending",
                        {"stage": "selection", "reason": "translation_unavailable"},
                    )
                context = _execution_context(context, thaw(scan.context))
                iterator = iter(scan)
                for ref in iterator:
                    if isinstance(ref, BranchEvent):
                        progress.update(ref)
                        continue
                    if not isinstance(ref, FieldReference):
                        raise QueryError(
                            "invalid_config",
                            "",
                            "backend must yield a field reference or branch event",
                        )
                    _validate_reference(ref, self._owner.configuration)
                    for qi, bi in ref.branches:
                        progress.started((qi, bi))
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
                        break
                else:
                    progress.finish()
            except BaseException as exc:
                failure = exc
                raise
            finally:
                _close_scan(iterator, scan, failure)
            execution_checks = getattr(scan, "checks", {})
        translations = plan_dict(plan)
        for t in translations:
            for check in execution_checks.get(t["query_index"], ()):
                existing = next(
                    (c for c in t["checks"] if c["code"] == check["code"]), None
                )
                if existing is None or check["code"] not in {
                    "context_resolved",
                    "return_metadata_sufficient",
                    "complete_retrieval_supported",
                    "request_association_verified",
                }:
                    raise QueryError(
                        "invalid_config",
                        "",
                        "backend returned an unplanned execution check",
                    )
                existing.update(thaw(check))
            for b in t["branches"]:
                b["execution"] = progress.execution((t["query_index"], b["index"]))
        report = _report(
            branches,
            plan,
            refs,
            policy,
            context,
            translations,
            progress,
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
    branches, plan, refs, policy, context, translations, progress, matched_queries
):
    summaries, missing_all, reasons_all = [], {}, []
    expected_all, satisfied_all = set(), set()
    unknown = False
    for b, expected in zip(branches, plan.expected):
        qi = b["index"]
        exhausted = progress.query_exhausted(qi)
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
    raw = query.to_dict()
    if (
        "member_role" in raw
        and "member" not in raw
        and "member" in scope
        and _count(scope["member"], "number") is not None
    ):
        # A product's default member domain is not an explicit user selection.
        # Resolve a role-only query within that finite domain before checking
        # explicit number/role contradictions. Never invent unknown roles.
        members = expand_queries(
            [{"member": scope["member"]}],
            max_expansion=configuration.execution_defaults["max_expansion"],
        )
        roles = [configuration.member_role(m.to_dict()["member"]) for m in members]
        if all(role is not None for role in roles):
            selected = [
                m.to_dict()["member"]
                for m, role in zip(members, roles)
                if _contains(raw["member_role"], role, "literal")
            ]
            if not selected:
                raise QueryError(
                    "constraint_conflict",
                    "/member_role",
                    "role is outside the source member domain",
                )
            scope["member"] = selected
    resources = configuration.resources
    parameter_ids = None
    if configuration.product is not None:
        parameter_ids = {
            name
            for provided in configuration.product["provides"]
            for name in (
                (provided["parameter"],)
                if isinstance(provided.get("parameter"), str)
                else provided.get("parameter", ())
            )
        }
    if "level_type" not in scope and _needs_vertical_type(scope):
        preliminary = (
            prepare_queries([query], resources, parameter_ids=parameter_ids)
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
                prepare_queries(
                    [value], resources, scope=bound, parameter_ids=parameter_ids
                )
                if resources is not None
                else (constrain_query(value, bound),)
            )
        return tuple(result)
    return (
        prepare_queries([query], resources, scope=scope, parameter_ids=parameter_ids)
        if resources is not None
        else (constrain_query(query, scope),)
    )


def expected_from_domain(queries, domain, configuration, *, identity_fields):
    """Pure projection of an independently defined COMPLETE finite domain.

    domain is None when provision is unknown, otherwise concrete declarations,
    never observations or a parameter-table row count. identity_fields states
    the product's applicable axes, supplied with independent applicability proof.
    This helper cannot establish that business proof, infer omitted applicability
    or compile a broad provides declaration into a complete product domain.
    Domain cardinality is NOT the execution max_expansion limit.
    """
    if domain is None:
        return tuple(None for _ in queries)
    if not identity_fields:
        raise QueryError(
            "invalid_config",
            "/expected_domain",
            "explicit applicable identity fields required",
        )
    fields = {
        "parameter",
        "level_type",
        "level",
        "level_unit",
        "layer",
        "time",
        "step",
        "valid_time",
        "member",
        "member_role",
        "native",
    }
    if isinstance(identity_fields, str) or not set(identity_fields) <= fields:
        raise QueryError(
            "invalid_config", "/expected_domain", "unknown applicable identity field"
        )
    rows = {}
    incomplete = False
    for index, value in enumerate(domain):
        try:
            values = (_expected_identity(value, configuration),)
            for q in values:
                row = q.to_dict()
                if not is_concrete(row) or len(expand_queries([q])) != 1:
                    raise QueryError(
                        "invalid_config", "", "domain identities must be concrete"
                    )
                if not set(identity_fields) <= row.keys():
                    incomplete = True
                product = configuration.product
                if product is not None and set(identity_fields) <= row.keys():
                    if not matches(row, thaw(product["scope"])) or not any(
                        matches(row, item.to_dict())
                        for item in prepare_queries(
                            thaw(product["provides"]), configuration.resources
                        )
                    ):
                        raise QueryError(
                            "invalid_config",
                            "",
                            "domain identity exceeds the declared product provision",
                        )
                if matches(row, configuration.scope):
                    rows[key(row)] = row
        except QueryError as exc:
            raise QueryError(
                "invalid_config",
                f"/expected_domain/{index}",
                exc.message,
            ) from exc
    if incomplete:
        return tuple(None for _ in queries)
    result = []
    for query in queries:
        query = normalize_query(query).to_dict()
        if "member_role" in query and any(
            "member" in row and "member_role" not in row for row in rows.values()
        ):
            result.append(None)
        else:
            result.append(tuple(row for row in rows.values() if matches(row, query)))
    return tuple(result)


def _expected_identity(value, configuration):
    values = (
        prepare_queries([value], configuration.resources)
        if configuration.resources is not None
        else (normalize_query(value),)
    )
    if len(values) != 1 or not is_concrete(values[0].to_dict()):
        raise QueryError("invalid_config", "", "expected identities must be concrete")
    row = values[0].to_dict()
    if "parameter" in row and configuration.resources is None:
        raise QueryError(
            "invalid_config",
            "/context/parameter_registry",
            "expected parameter needs its registry",
        )
    if "member" in row:
        role = configuration.member_role(row["member"])
        if role is not None:
            if "member_role" in row and row["member_role"] != role:
                raise QueryError(
                    "invalid_config",
                    "",
                    "expected member role contradicts configuration",
                )
            row["member_role"] = role
    return normalize_query(row)


def _check_member_roles(query, configuration):
    """Validate explicit role contradictions without expanding other dimensions."""
    row = query.to_dict()
    if "member" not in row or "member_role" not in row:
        return
    selector, roles = row["member"], row["member_role"]
    roles = set(roles if isinstance(roles, list) else [roles])
    known = {int(k): v for k, v in configuration.member_roles.items()}
    conflict = any(
        _contains(selector, member, "number") and role not in roles
        for member, role in known.items()
    )
    if configuration.cemc_member_roles:
        if (
            0 not in known
            and _contains(selector, 0, "number")
            and "control" not in roles
        ):
            conflict = True
        # All member selectors are integral. Count a continuous integer range
        # with the shared selector arithmetic, without enumerating its members.
        countable = selector
        if isinstance(selector, dict) and "every" not in selector["range"]:
            countable = {"range": {**selector["range"], "every": 1}}
        positives = _count(countable, "number") - int(_contains(selector, 0, "number"))
        overrides = sum(m > 0 and _contains(selector, m, "number") for m in known)
        if positives > overrides and "perturbation" not in roles:
            conflict = True
    if conflict:
        raise QueryError(
            "constraint_conflict",
            "/member_role",
            "member number conflicts with the effective role mapping",
            {"reason": "fixed_condition_conflict"},
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
    # scopes, versions or defaults. Reserved software origins may be appended;
    # existing configuration provenance is never overwritten. No client/request body.
    if (
        set(extra) - {"source", "origins"}
        or set(extra.get("origins", {})) - {"adapter", "native_library"}
        or set(extra.get("source", {}))
        - {
            "paths",
            "fingerprints",
            "version",
        }
    ):
        raise QueryError(
            "invalid_config", "", "backend returned unsupported report context"
        )
    for name, value in extra.get("origins", {}).items():
        if name in context.get("origins", {}) and context["origins"][name] != value:
            raise QueryError(
                "invalid_config", "", "backend cannot replace configuration provenance"
            )
    return {
        **context,
        "source": {**context.get("source", {}), **extra.get("source", {})},
        "origins": {**context.get("origins", {}), **extra.get("origins", {})},
    }
