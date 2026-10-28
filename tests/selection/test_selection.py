"""Core behavior with a controlled metadata/value backend only."""

from dataclasses import replace
import json

import pytest

from cedarkit_query import (
    Query,
    QueryError,
    SourceError,
    CompletenessError,
    QueryReport,
)
from reki import from_source
from reki.selection.core import matches


def changed(q, **values):
    data = q.to_dict()
    data.pop("valid_time", None)
    return Query({**data, **values})


def test_shared_public_models():
    import reki
    import cedarkit_query

    for name in (
        "Query",
        "Request",
        "QueryReport",
        "QueryExplanation",
        "QueryError",
        "SourceError",
        "CompletenessError",
    ):
        assert getattr(reki, name) is getattr(cedarkit_query, name)


def test_construction_and_explain_no_business_io(factory, q):
    source, backend, _ = factory([q], [q])
    selected = source.sel(q)
    info = selected.explain()
    assert (backend.starts, backend.visits, backend.loads) == (0, 0, 0)
    assert info.analysis["expected_count"] == 1
    assert info.analysis["translations"][0]["coverage"]["status"] == "passed"
    assert "execution" not in info.analysis["translations"][0]["branches"][0]
    assert info.context["definitions"][0]["sha256"]
    copy = info.to_dict()
    copy["effective_queries"].clear()
    assert len(info.effective_queries) == 1


def test_union_intersection_origins_and_aliases(factory, q):
    other = changed(q, level=500, step="PT12H")
    source, backend, _ = factory([q, other], [q, other])
    selected = source.sel([changed(q, parameter="t"), q, other]).sel(
        level_type="pressure", level=500
    )
    info = selected.explain()
    assert len(info.effective_queries) == 1
    assert [dict(o) for o in info.effective_queries[0]["origins"]] == [
        dict(step_index=0, query_index=2),
        dict(step_index=1, query_index=0),
    ]
    assert len(selected.all()) == 1
    assert backend.loads == 0
    duplicate = source.sel([changed(q, parameter="t"), q]).explain()
    assert [dict(o) for o in duplicate.effective_queries[0]["origins"]] == [
        dict(step_index=0, query_index=0),
        dict(step_index=0, query_index=1),
    ]


def test_empty_intersection_does_not_hide_later_invalid(factory, q):
    source, backend, _ = factory([q], [q])
    selected = source.sel(q).sel(level_type="pressure", level=500)
    assert selected.explain().analysis["expected_count"] == 0
    assert len(selected.all()) == 0
    assert backend.starts == 0
    assert not selected.to_xarray().data_vars
    with pytest.raises(QueryError):
        selected.sel(parameter="not-registered")
    with pytest.raises(QueryError):
        selected.sel(member=-1)


def test_fixed_scope_conflict_even_after_empty(factory, q):
    source, _, _ = factory([], [], context={"scope": {"member": 0}})
    empty = source.sel(q).sel(level_type="pressure", level=500)
    with pytest.raises(QueryError) as exc:
        empty.sel(member=[0, 1])
    assert exc.value.code == "constraint_conflict"


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, "2"])
def test_invalid_expansion_limit(factory, limit):
    with pytest.raises(QueryError) as exc:
        factory(context={"execution": {"max_expansion": limit}})
    assert exc.value.code == "invalid_config"


def test_expansion_limit_no_truncation_and_no_field_count_limit(factory, q):
    source, backend, _ = factory(
        [q] * 5, [q], context={"execution": {"max_expansion": 2}}
    )
    assert (
        len(source.sel(q).all()) == 5
    )  # distinct records, one discrete Query identity
    with pytest.raises(QueryError) as exc:
        source.sel(changed(q, level=[850, 700, 500]))
    assert exc.value.code == "expansion_limit_exceeded"
    assert exc.value.context["limit"] == 2
    assert backend.loads == 0


def test_stable_first_early_stop_and_no_match(factory, q):
    other = changed(q, level=500)
    source, backend, refs = factory([q, other], [q, other], branches=2)
    first = source.sel([other, q]).first()
    assert first._reference.record_id == refs[0].record_id
    assert backend.visits == 1 and backend.loads == 0
    report = first.report
    assert report.overall["status"] == "unchecked" and not report.overall["missing"]
    assert (
        report.translations[0]["branches"][0]["execution"]["status"] == "stopped_early"
    )
    assert report.translations[0]["branches"][1]["execution"]["status"] == "not_started"
    assert source.sel([other, q]).all().first().identity == first.identity
    assert source.sel(changed(q, level=700)).first() is None


def test_one_counts_records_not_business_id_and_deduplicates_same_record(factory, q):
    source, backend, refs = factory([q], [q])
    backend.records = refs * 2
    assert source.sel(q).one().identity == refs[0].identity
    backend.records = [refs[0], replace(refs[0], record_id="SYNTHETIC:another-record")]
    with pytest.raises(QueryError) as exc:
        source.sel(q).one()
    assert exc.value.code == "multiple_matches" and "report" not in exc.value.to_dict()
    assert len(source.sel(q).all()) == 2
    with pytest.raises(QueryError) as exc:
        source.sel(q).to_xarray()
    assert exc.value.code == "duplicate_field"
    assert backend.loads == 0


def test_required_precedes_cardinality_and_cannot_guess_expected(factory, q):
    absent = changed(q, level=500)
    source, backend, _ = factory([q], [q, absent])
    selection = source.sel(changed(q, level=[850, 500]))
    for terminal in (
        selection.first,
        selection.one,
        selection.all,
        selection.to_xarray,
    ):
        with pytest.raises(CompletenessError) as exc:
            terminal(completeness="required")
        assert exc.value.code == "missing_fields"
        assert exc.value.report.overall["expected_count"] == 2
        assert exc.value.to_dict()["report"]["overall"]["status"] == "missing"
    assert backend.loads == 0
    unknown, _, _ = factory([q], None)
    with pytest.raises(CompletenessError) as exc:
        unknown.sel(q).one(completeness="required")
    assert exc.value.code == "completeness_undetermined"
    assert exc.value.report.overall["expected_count"] is None


def test_default_policy_override_does_not_mutate(factory, q):
    source, _, _ = factory(
        [q], None, context={"execution": {"completeness": "required"}}
    )
    selection = source.sel(q)
    assert selection.one(completeness="available").report.completeness == "available"
    with pytest.raises(CompletenessError):
        selection.one()


def test_empty_required_expected_zero_vs_missing(factory, q):
    source, _, _ = factory([], [q])
    with pytest.raises(CompletenessError):
        source.sel(q).one(completeness="required")
    with pytest.raises(QueryError) as exc:
        source.sel(q).sel(level_type="pressure", level=500).one(completeness="required")
    assert exc.value.code == "no_match"


def test_candidate_and_empty_residual_never_replace_full_query(factory, q):
    mismatch = changed(q, level=500)
    source, _, _ = factory([mismatch, q], [q])
    assert source.sel(q).one().identity.level == 850
    assert not matches(Query(parameter="synthetic.t"), q)
    source, _, _ = factory([q], [q], residual={"member": 2})
    assert len(source.sel(q).all()) == 0


def test_source_failures_not_missing_or_early_stop(factory, q):
    source, backend, refs = factory([q], [q])
    failure = SourceError(
        "incomplete_response",
        "",
        "SYNTHETIC pagination failure",
        {"reason": "pagination_incomplete"},
    )
    backend.records = [refs[0], failure]
    assert source.sel(q).first().identity == refs[0].identity
    for terminal in (source.sel(q).all, source.sel(q).one):
        with pytest.raises(SourceError) as exc:
            terminal()
        assert exc.value is failure and "report" not in exc.value.to_dict()
    assert backend.scan_closes == 3


def test_finite_file_backend_does_not_turn_invalid_input_into_business_missing(
    tmp_path,
):
    file = tmp_path / "SYNTHETIC"
    file.write_bytes(b"x")
    with from_source({"kind": "file", "path": str(file)}) as source:
        selection = source.sel(native={"grib": {"discipline": 0}})
        assert (
            selection.explain().analysis["translations"][0]["coverage"]["status"]
            == "passed"
        )
        with pytest.raises(SourceError) as exc:
            selection.all()
        assert exc.value.code == "decode_failed"


def test_source_path_configuration_checked_without_discovery(tmp_path):
    with pytest.raises(SourceError) as exc:
        from_source({"kind": "file", "path": str(tmp_path / "absent")})
    assert exc.value.code == "resource_not_found"
    with from_source(
        {"kind": "file", "directory": str(tmp_path), "glob": "*.grib2"}
    ) as source:
        assert source.sel().explain().context["source"]["kind"] == "file"


def test_lifecycle_snapshot_and_no_query_or_value_cache(factory, q):
    source, backend, _ = factory([q], [q])
    selected = source.sel(q)
    fields = selected.all()
    ds = fields.to_xarray()
    fields.to_xarray()
    assert backend.loads == 2 and backend.starts == 1
    selected.all()
    assert backend.starts == 2
    source.close()
    source.close()
    assert backend.closes == 1
    assert fields[0].metadata and fields.report.overall["status"] == "complete"
    for action in (selected.all, fields.to_xarray, fields[0].to_xarray):
        with pytest.raises(SourceError):
            action()
    assert float(ds.t.values.flat[0]) == 1


def test_report_snapshot_is_json_independent_and_no_values_claim(factory, q):
    source, backend, _ = factory([q], [q])
    fields = source.sel(q).all()
    assert backend.loads == 0
    ds = fields.to_xarray()
    report = QueryReport.from_json(ds.attrs["cedarkit_query_report"])
    assert report == fields.report
    assert ds.t.attrs["cedarkit_query_report"] == report.to_json()
    assert "execution" in report.translations[0]["branches"][0]
    assert "array" not in json.dumps(report.to_dict())


def test_report_union_counts_identities_once(factory, q):
    q500 = changed(q, level=500)
    source, _, _ = factory([q], [q, q500])
    fields = source.sel([q, changed(q, level=[850, 500])]).all()
    assert fields.report.overall["expected_count"] == 2
    assert fields.report.overall["satisfied_count"] == 1
    assert fields.report.overall["field_count"] == 1
    assert len(fields.report.overall["missing"]) == 1
    assert len(fields.report.queries) == 2


def test_mixed_known_missing_and_unknown_report_preserves_both(factory, q):
    from reki.selection.backend import Plan

    source, backend, _ = factory([], [q])
    ordinary = backend.plan

    def plan(queries, configuration):
        p = ordinary(queries, configuration)
        return Plan(
            p.translations,
            tuple(
                rows if query.to_dict().get("level") == 850 else None
                for query, rows in zip(queries, p.expected)
            ),
        )

    backend.plan = plan
    selected = source.sel([q, changed(q, level=500)])
    with pytest.raises(CompletenessError) as exc:
        selected.all(completeness="required")
    report = exc.value.report
    assert exc.value.code == "missing_fields"
    assert report.overall["expected_count"] is None
    assert report.overall["missing"] and report.overall["reasons"]


def test_dynamic_plan_refinement_is_terminal_only(factory, q):
    from reki.selection.backend import Plan

    source, backend, _ = factory([q], [q], pending=True)
    ordinary = backend.start

    def start(plan):
        scan = ordinary(plan)
        data = [dict(t) for t in plan.translations]
        data[0]["coverage"] = dict(
            status="passed", message="SYNTHETIC acquired context"
        )
        scan.plan = Plan(tuple(data), plan.expected)
        return scan

    backend.start = start
    selected = source.sel(q)
    assert (
        selected.explain().analysis["translations"][0]["coverage"]["status"]
        == "pending"
    )
    result = selected.all(completeness="required")
    assert result.report.translations[0]["coverage"]["status"] == "passed"
    assert backend.starts == 1 and backend.loads == 0


def test_plan_basis_links_and_context_injection_are_rejected(factory, q):
    from reki.selection.backend import Plan
    from reki.catalog.model import thaw

    source, backend, _ = factory([q], [q])
    ordinary = backend.plan

    def invalid(queries, configuration):
        p = ordinary(queries, configuration)
        data = thaw(p.translations)
        data[0]["branches"][0]["basis"] = [
            dict(kind="mapping", resource=dict(kind="mappings", id="ABSENT"))
        ]
        return Plan(tuple(data), p.expected)

    backend.plan = invalid
    with pytest.raises(QueryError):
        source.sel(q)
    assert backend.starts == 0
    backend.plan = ordinary
    start = backend.start

    def invalid_context(plan):
        scan = start(plan)
        scan.context = {"client": "SYNTHETIC-secret"}
        return scan

    backend.start = invalid_context
    with pytest.raises(QueryError) as exc:
        source.sel(q).all()
    assert "SYNTHETIC-secret" not in json.dumps(exc.value.to_dict())


def test_duplicate_reference_mutation_and_fixed_metadata_are_source_errors(factory, q):
    source, backend, refs = factory([q], [q])
    backend.records = [refs[0], replace(refs[0], grid={"id": "changed"})]
    with pytest.raises(SourceError) as exc:
        source.sel(q).all()
    assert exc.value.context["reason"] == "inconsistent_native_metadata"
    backend.records = [
        replace(
            refs[0], metadata={**dict(refs[0].metadata), "parameter_name": "invented"}
        )
    ]
    with pytest.raises(SourceError) as exc:
        source.sel(q).all()
    assert exc.value.context["reason"] == "fixed_definition_mismatch"


def test_error_origin_and_readonly_source_configuration(factory, q):
    source, _, _ = factory([q], [q])
    with pytest.raises(QueryError) as exc:
        source.sel([q, {"member": -1}])
    assert exc.value.path.startswith("/queries/1/member")
    assert [dict(o) for o in exc.value.context["origins"]] == [
        dict(step_index=0, query_index=1)
    ]
    with pytest.raises(AttributeError):
        source.configuration = source.configuration
    with pytest.raises(TypeError):
        source.configuration.execution_defaults["max_expansion"] = 1


def test_external_client_is_not_closed_and_no_connection_call(tmp_path):
    class Client:
        calls = closes = 0

        def close(self):
            self.closes += 1

        def request(self):
            self.calls += 1

    client = Client()
    with pytest.raises(QueryError):
        from_source({"kind": "cmadaas", "dataset": "UNKNOWN-SYNTHETIC"}, client=client)
    assert client.calls == client.closes == 0


def test_continuous_explanation_not_finite_expansion_count(factory, q):
    source, _, _ = factory([q], None)
    selected = source.sel(changed(q, level={"range": {"start": 500, "end": 850}}))
    assert selected.explain().analysis["expansion_count"] is None
    assert selected.explain().analysis["expected_count"] is None


def test_one_stops_on_second_distinct_record_unless_required(factory, q):
    source, backend, refs = factory([q, q], [q])
    failure = SourceError("timeout", "", "SYNTHETIC later acquisition failure")
    backend.records = [*refs, failure]
    with pytest.raises(QueryError) as exc:
        source.sel(q).one()
    assert exc.value.code == "multiple_matches" and backend.visits == 2
    with pytest.raises(SourceError) as exc:
        source.sel(q).one(completeness="required")
    assert exc.value is failure


def test_documented_public_inspection_example(tmp_path, monkeypatch):
    from pathlib import Path

    document = (
        Path(__file__).parents[2] / "doc/source/development/architecture/query-core.md"
    )
    snippet = document.read_text().split("```python\n", 1)[1].split("```", 1)[0]
    monkeypatch.chdir(tmp_path)
    exec(compile(snippet, str(document), "exec"), {})


def test_partial_chained_vertical_selector_uses_established_type(factory, q):
    other = changed(q, level=500, step="PT12H")
    source, _, _ = factory([q, other], [q, other])
    selection = source.sel([q, other]).sel(level=500)
    explanation = selection.explain()
    assert explanation.steps[1]["input_queries"][0] == {"level": 500}
    assert explanation.effective_queries[0]["query"]["level_type"] == "pressure"
    assert selection.one().identity.level == 500
    assert len(selection.sel(level=850).all()) == 0


def test_partial_vertical_scope_binds_only_to_proven_query_type(factory, q):
    source, _, _ = factory([q], [q], context={"scope": {"level": 850}})
    assert source.sel(q).one().identity.level == 850
    with pytest.raises(QueryError) as exc:
        source.sel(changed(q, level=500))
    assert exc.value.code == "constraint_conflict"
