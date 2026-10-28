"""I05 round 2: independent expectations and scripted acquisition, all SYNTHETIC."""

from dataclasses import replace
import json

import numpy as np
import pytest
import xarray as xr

from cedarkit_query import Query, QueryError, SourceError, CompletenessError
from reki.catalog.model import thaw
from reki.selection.backend import Plan, BranchEvent
from reki.selection.core import expected_from_domain


def change(q, **values):
    data = q.to_dict()
    data.pop("valid_time", None)
    return Query({**data, **values})


class ScriptedScan:
    def __init__(self, backend, plan, events, cleanup_failure=None):
        self.backend, self.plan, self.context = backend, plan, {}
        self.events, self.cleanup_failure = events, cleanup_failure

    def __iter__(self):
        try:
            for item in self.events(self.plan):
                if isinstance(item, BaseException):
                    raise item
                yield item
        finally:
            self.backend.iterator_closes += 1

    def close(self):
        self.backend.scan_closes += 1
        if self.cleanup_failure is not None:
            raise self.cleanup_failure


def scripted(backend, events, *, plan_builder=None, refine=None, cleanup_failure=None):
    backend.iterator_closes = 0
    original = backend.plan
    if plan_builder is not None:
        backend.plan = lambda queries, configuration: plan_builder(
            original(queries, configuration)
        )

    def start(plan):
        backend.starts += 1
        return ScriptedScan(
            backend, plan if refine is None else refine(plan), events, cleanup_failure
        )

    backend.start = start


def two_branches(plan):
    data = thaw(plan.translations)
    for item in data:
        first = item["branches"][0]
        item["branches"] = [
            {
                **first,
                "index": 0,
                "candidate_filter": {"parameterNumber": 1},
                "residual": {"level_type": "pressure", "level": 850},
            },
            {
                **first,
                "index": 1,
                "candidate_filter": {"parameterNumber": 2},
                "residual": {"level_type": "pressure", "level": 500},
            },
        ]
    return Plan(tuple(data), plan.expected)


def test_first_preserves_empty_exhausted_active_and_unstarted_branches(factory, q):
    lower = change(q, level=500)
    source, backend, refs = factory([lower], [q, lower])

    def plan_builder(plan):
        p = two_branches(plan)
        data = thaw(p.translations)
        data[0]["branches"].append({**data[0]["branches"][1], "index": 2})
        return Plan(tuple(data), p.expected)

    def events(plan):
        yield BranchEvent(0, 0, "started")
        yield BranchEvent(0, 0, "exhausted")
        yield BranchEvent(0, 1, "started")
        yield replace(refs[0], branches=((0, 1),))
        raise AssertionError("first must stop here")

    scripted(backend, events, plan_builder=plan_builder)
    selected = source.sel(change(q, level=[850, 500]))
    result = selected.first()
    statuses = [
        b["execution"]["status"] for b in result.report.translations[0]["branches"]
    ]
    assert statuses == ["exhausted", "stopped_early", "not_started"]
    assert result.report.overall["status"] == "unchecked"
    assert not result.report.overall[
        "missing"
    ]  # Other branches could still satisfy q850.
    assert backend.iterator_closes == backend.scan_closes == 1 and backend.loads == 0


def test_first_reports_proven_missing_query_separately_from_unexhausted_query(
    factory, q
):
    lower = change(q, level=500)
    source, backend, refs = factory([lower], [q, lower])

    def events(plan):
        index850 = next(
            t["query_index"] for t in plan.translations if t["query_index"] != 0
        )
        yield BranchEvent(index850, 0, "started")
        yield BranchEvent(index850, 0, "exhausted")
        yield replace(refs[0], branches=((0, 0),))

    scripted(backend, events)
    result = source.sel([q, lower]).first()
    assert result.report.overall["status"] == "missing"
    assert len(result.report.overall["missing"]) == 1
    assert result.report.overall["missing"][0]["selection"]["level"] == 850
    assert result.report.overall["reasons"][0]["query_indexes"] == (0,)


def test_paired_residuals_never_cross_and_complete_query_still_checked(factory, q):
    lower = change(q, level=500)
    outside = change(q, level=700)
    source, backend, refs = factory([q, lower, outside], [q, lower])

    def events(plan):
        yield BranchEvent(0, 0, "started")
        yield BranchEvent(0, 1, "started")
        # Each of the first two is in the OTHER branch's residual, hence rejected.
        yield replace(refs[0], branches=((0, 1),))
        yield replace(refs[1], branches=((0, 0),))
        yield replace(refs[2], branches=((0, 0),))
        yield replace(refs[0], branches=((0, 0),))
        yield replace(refs[1], branches=((0, 1),))
        # Same physical record reached through overlapping candidate branches.
        yield replace(refs[0], branches=((0, 0), (0, 1)))
        yield BranchEvent(0, 0, "exhausted")
        yield BranchEvent(0, 1, "exhausted")

    scripted(backend, events, plan_builder=two_branches)
    result = source.sel(change(q, level=[850, 500])).all(completeness="required")
    assert [f.identity.level for f in result] == [850, 500]
    assert result.report.overall["field_count"] == 2
    assert result.report.overall["expected_count"] == 2
    assert all(
        b["execution"]["status"] == "exhausted"
        for b in result.report.translations[0]["branches"]
    )
    explanation = source.sel(change(q, level=[850, 500])).explain()
    branches = explanation.analysis["translations"][0]["branches"]
    assert branches[0]["candidate_filter"]["parameterNumber"] == 1
    assert branches[0]["residual"]["level"] == 850
    assert branches[1]["candidate_filter"]["parameterNumber"] == 2
    assert branches[1]["residual"]["level"] == 500
    assert backend.loads == 0


@pytest.mark.parametrize(
    "events",
    [
        lambda ref: [BranchEvent(0, 1, "started")],
        lambda ref: [BranchEvent(0, 0, "exhausted")],
        lambda ref: [BranchEvent(0, 0, "started"), BranchEvent(0, 0, "exhausted"), ref],
    ],
)
def test_invalid_branch_progress_is_not_a_successful_empty_result(factory, q, events):
    source, backend, refs = factory([q], [q])
    scripted(backend, lambda plan: events(refs[0]))
    with pytest.raises(QueryError) as exc:
        source.sel(q).all()
    assert exc.value.code == "invalid_config"
    assert backend.iterator_closes == backend.scan_closes == 1


def test_all_on_shared_scan_can_certify_empty_branches_without_repeated_io(factory, q):
    source, backend, _ = factory([], [q])
    scripted(backend, lambda plan: [], plan_builder=two_branches)
    result = source.sel(q).all()
    assert result.report.overall["status"] == "missing"
    assert all(
        b["execution"]["status"] == "exhausted"
        for b in result.report.translations[0]["branches"]
    )
    assert backend.starts == backend.scan_closes == 1


def test_branch_exhaustion_cannot_hide_later_acquisition_failure(factory, q):
    source, backend, _ = factory([], [q])
    failure = SourceError(
        "incomplete_response",
        "",
        "SYNTHETIC truncated acquisition",
        {"reason": "response_truncated"},
    )
    scripted(
        backend,
        lambda plan: [
            BranchEvent(0, 0, "started"),
            BranchEvent(0, 0, "exhausted"),
            failure,
        ],
    )
    with pytest.raises(SourceError) as exc:
        source.sel(q).all()
    assert exc.value is failure and "report" not in failure.to_dict()
    assert backend.iterator_closes == backend.scan_closes == 1


def test_combined_expansion_limit_keeps_all_contributing_origins(factory, q):
    source, _, _ = factory([], None, context={"execution": {"max_expansion": 3}})
    with pytest.raises(QueryError) as exc:
        source.sel([change(q, level=[850, 700]), change(q, level=[500, 300])])
    assert exc.value.code == "expansion_limit_exceeded" and exc.value.path == "/queries"
    assert thaw(exc.value.context["origins"]) == [
        dict(step_index=0, query_index=0),
        dict(step_index=0, query_index=1),
    ]
    assert exc.value.context["limit"] == 3


def test_configuration_and_backend_paths_are_not_rebased_to_last_query(factory, q):
    source, _, _ = factory([], None, no_resources=True)
    with pytest.raises(QueryError) as exc:
        source.sel(q)
    assert exc.value.path == "/context/parameter_registry"
    source, backend, _ = factory([], None)

    def plan(queries, configuration):
        raise QueryError(
            "invalid_config",
            "/tables/0/rows/1",
            "SYNTHETIC invalid table",
            {"document": "SYNTHETIC-mappings.json"},
        )

    backend.plan = plan
    with pytest.raises(QueryError) as exc:
        source.sel([q, change(q, level=500)])
    assert exc.value.path == "/tables/0/rows/1"
    assert exc.value.context["document"] == "SYNTHETIC-mappings.json"
    assert len(exc.value.context["origins"]) == 2


def test_backend_effective_query_index_maps_to_original_inputs(factory, q):
    source, backend, _ = factory([], None)

    def plan(queries, configuration):
        index = next(i for i, q in enumerate(queries) if q.level == 500)
        raise QueryError(
            "unsupported",
            "/queries",
            "SYNTHETIC unsupported slice",
            {"query_index": index},
        )

    backend.plan = plan
    with pytest.raises(QueryError) as exc:
        source.sel([q, change(q, level=500), change(q, level=500)])
    assert thaw(exc.value.context["origins"]) == [
        dict(step_index=0, query_index=1),
        dict(step_index=0, query_index=2),
    ]


def test_independent_domain_uses_definitions_units_pairing_roles_and_no_observations(
    factory, q
):
    other = change(q, level=500, step="PT12H", member=2, member_role="perturbation")
    first = change(q, member=0, member_role="control")
    source, backend, refs = factory(
        [first],
        [first, other],
        context={"member_roles": {"0": "control", "2": "perturbation"}},
    )
    declared_first = change(first, parameter="t", level=85000, level_unit="Pa")
    declared_other = other.to_dict()
    declared_other.pop("member_role")
    # Complete independent declarations, deliberately not built from backend.records.
    domain = [declared_first, Query(declared_other), declared_first]
    original = backend.plan

    def plan(queries, configuration):
        p = original(queries, configuration)
        expected = expected_from_domain(
            queries,
            domain,
            configuration,
            identity_fields=(
                "parameter",
                "level_type",
                "level",
                "time",
                "step",
                "member",
            ),
        )
        return Plan(p.translations, expected)

    backend.plan = plan
    selected = source.sel([first, other])
    assert selected.explain().analysis["expected_count"] == 2 and backend.starts == 0
    with pytest.raises(CompletenessError) as exc:
        selected.all(completeness="required")
    assert exc.value.report.overall["expected_count"] == 2
    assert (
        exc.value.report.overall["missing"][0]["selection"]["member_role"]
        == "perturbation"
    )
    backend.records = []
    assert selected.all().report.overall["expected_count"] == 2
    assert backend.loads == 0


def test_unknown_incomplete_and_known_empty_domains_are_distinct(factory, q):
    source, _, _ = factory()
    config = source.configuration
    required = ("parameter", "time", "step")
    assert expected_from_domain([q], None, config, identity_fields=required) == (None,)
    assert expected_from_domain(
        [q], [Query(parameter="synthetic.t")], config, identity_fields=required
    ) == (None,)
    assert expected_from_domain([q], [], config, identity_fields=required) == ((),)


def test_domain_cardinality_is_not_the_query_expansion_limit(factory, q):
    source, _, _ = factory(context={"execution": {"max_expansion": 1}})
    domain = [q, change(q, level=500), change(q, level=300)]
    expected = expected_from_domain(
        [Query(parameter="synthetic.t")],
        domain,
        source.configuration,
        identity_fields=("parameter", "level_type", "level", "time", "step"),
    )
    assert len(expected[0]) == 3


def test_start_cannot_replace_static_expected_set_with_observed_subset(factory, q):
    source, backend, refs = factory([q], [q, change(q, level=500)])
    scripted(
        backend,
        lambda plan: refs,
        refine=lambda plan: Plan(plan.translations, ((q.to_dict(),),)),
    )
    with pytest.raises(QueryError) as exc:
        source.sel(change(q, level=[850, 500])).all()
    assert exc.value.code == "invalid_config" and backend.loads == 0
    assert backend.scan_closes == 1


def test_iterator_cleanup_preserves_primary_error_and_closes_scan(factory, q):
    source, backend, _ = factory([], [q])
    primary = SourceError("timeout", "", "SYNTHETIC acquisition failure")
    cleanup = SourceError("io_error", "", "SYNTHETIC cleanup failure")
    scripted(backend, lambda plan: [primary], cleanup_failure=cleanup)
    with pytest.raises(SourceError) as exc:
        source.sel(q).all()
    assert exc.value is primary
    assert backend.iterator_closes == backend.scan_closes == 1
    assert "SYNTHETIC cleanup failure" not in json.dumps(primary.to_dict())


def test_successful_query_does_not_return_results_if_cleanup_fails(factory, q):
    source, backend, refs = factory([q], [q])
    cleanup = SourceError("io_error", "", "SYNTHETIC cleanup failure")
    scripted(backend, lambda plan: refs, cleanup_failure=cleanup)
    with pytest.raises(SourceError) as exc:
        source.sel(q).first()
    assert exc.value is cleanup and backend.iterator_closes == backend.scan_closes == 1


def test_loaded_values_remain_independent_but_conversion_cannot_continue_after_close(
    factory, q
):
    source, backend, refs = factory([q], [q])

    def load():
        source.close()
        return xr.DataArray(
            np.ones((2, 2)),
            dims=("latitude", "longitude"),
            coords={"latitude": [45.0, 40.0], "longitude": [100.0, 105.0]},
        )

    backend.records = [replace(refs[0], load=load)]
    fields = source.sel(q).all()
    with pytest.raises(SourceError):
        fields.to_xarray()
    assert fields.report.overall["status"] == "complete" and fields[0].metadata


def product_configuration(tmp_path):
    from pathlib import Path
    from reki.catalog import plan_source_binding

    tmp_path = tmp_path / "SYNTHETIC-product"
    tmp_path.mkdir()

    bundle = json.loads(
        (Path(__file__).parent / "fixtures/independent-domain-v1.json").read_text()
    )
    for role in ("parameters", "mappings", "catalog"):
        (tmp_path / (role + ".json")).write_text(json.dumps(bundle[role]))
    file = tmp_path / "SYNTHETIC.not-grib"
    file.write_bytes(b"SYNTHETIC placeholder; no decoder is invoked")
    configuration = plan_source_binding(
        {"kind": "file", "path": str(file), "dataset": "SYNTHETIC.i05"},
        context={
            "catalog": {"path": str(tmp_path / "catalog.json")},
            "parameter_registry": {"path": str(tmp_path / "parameters.json")},
        },
        product="SYNTHETIC.paired",
        product_version="SYNTHETIC-v1",
    )
    return bundle, configuration


def test_i04_resources_to_versioned_domain_to_report_without_business_io(
    factory, q, tmp_path
):
    from reki.selection.core import construct_source

    bundle, configuration = product_configuration(tmp_path)
    _, backend, refs = factory([q], None)
    source = construct_source(configuration, backend)
    original = backend.plan

    def plan(queries, configuration):
        p = original(queries, configuration)
        translations = thaw(p.translations)
        for t in translations:
            t["branches"][0]["basis"] = [
                dict(
                    kind="mapping",
                    resource={"kind": "mappings", "id": "SYNTHETIC.i05.grib"},
                    mapping="SYNTHETIC.temperature",
                    responsibility="vertical",
                    rule="grib.fixed_surfaces",
                )
            ]
        return Plan(
            tuple(translations),
            expected_from_domain(
                queries,
                bundle["domain"],
                configuration,
                identity_fields=bundle["identity_fields"],
            ),
        )

    backend.plan = plan
    selected = source.sel(parameter="t")
    info = selected.explain()
    assert info.analysis["expected_count"] == 2 and backend.starts == backend.loads == 0
    assert info.context["source"]["product_version"] == "SYNTHETIC-v1"
    assert {r["role"] for r in info.context["definitions"]} == {
        "catalog",
        "parameter_registry",
        "mappings",
    }
    result = selected.all()
    assert (
        result.report.overall["expected_count"] == 2
        and result.report.overall["satisfied_count"] == 1
    )
    missing = result.report.overall["missing"][0]["selection"]
    assert missing["level"] == 500 and missing["step"] == "PT43200S"
    assert result.to_xarray().sizes["pressure"] == 1
    assert backend.loads == 1


def test_independent_domain_cannot_expand_the_declared_product(factory, q, tmp_path):
    bundle, configuration = product_configuration(tmp_path)
    invalid = [*bundle["domain"], change(q, level=700)]
    with pytest.raises(QueryError) as exc:
        expected_from_domain(
            [q], invalid, configuration, identity_fields=bundle["identity_fields"]
        )
    assert exc.value.code == "invalid_config" and exc.value.path == "/expected_domain/2"


def test_candidate_scope_cannot_expand_known_identity_or_time(factory, q, tmp_path):
    from reki.selection.core import construct_source

    _, configuration = product_configuration(tmp_path)
    _, backend, _ = factory([q], [q])
    source = construct_source(configuration, backend)
    original = backend.plan
    for scope in (
        {"product_version": "SYNTHETIC-other"},
        {"time": "2026-01-02T00:00:00Z"},
    ):

        def plan(queries, config):
            p = original(queries, config)
            data = thaw(p.translations)
            data[0]["branches"][0]["scope"] = scope
            return Plan(tuple(data), p.expected)

        backend.plan = plan
        with pytest.raises(QueryError) as exc:
            source.sel(q)
        assert exc.value.code == "invalid_config"
        assert exc.value.path.startswith("/translations/0/branches/0/scope/")
    assert backend.starts == backend.loads == 0


def test_incomplete_domain_does_not_hide_invalid_later_declaration(factory, q):
    source, _, _ = factory()
    with pytest.raises(QueryError) as exc:
        expected_from_domain(
            [q],
            [Query(parameter="synthetic.t"), Query(parameter="UNKNOWN")],
            source.configuration,
            identity_fields=("parameter", "time", "step"),
        )
    assert exc.value.path == "/expected_domain/1"


def test_successful_external_and_owned_client_lifetimes_are_separate(factory, q):
    class Client:
        closes = calls = 0

        def close(self):
            self.closes += 1

    for owned in (False, True):
        client = Client()
        source, backend, refs = factory([q], [q])
        original_close = backend.close

        def close():
            original_close()
            if owned:
                client.close()

        backend.close = close
        with source:
            ds = source.sel(q).to_xarray()
        source.close()
        assert client.closes == int(owned) and client.calls == 0
        assert backend.closes == 1 and float(ds.t.values.flat[0]) == 1
        with pytest.raises(SourceError):
            source.sel(q)


def test_value_load_failure_is_not_a_completeness_failure_or_partial_dataset(
    factory, q
):
    lower = change(q, level=500)
    source, backend, refs = factory([q, lower], [q, lower])
    failure = SourceError("decode_failed", "", "SYNTHETIC value decode failure")

    def bad_load():
        raise failure

    backend.records = [refs[0], replace(refs[1], load=bad_load)]
    fields = source.sel([q, lower]).all(completeness="required")
    assert (
        fields.report.overall["status"] == "complete"
    )  # Presence is not value quality.
    with pytest.raises(SourceError) as exc:
        fields.to_xarray()
    assert exc.value is failure and "report" not in failure.to_dict()
    assert fields.report.overall["status"] == "complete"


def test_depth_axis_and_shared_actual_coordinate_domain(factory, q):
    deep = change(q, level_type="depth_below_land", level=40, level_unit="cm")
    shallow = change(q, level_type="depth_below_land", level=10, level_unit="cm")
    source, _, _ = factory([deep, shallow], [deep, shallow])
    ds = source.sel([deep, shallow]).to_xarray()
    np.testing.assert_array_equal(ds.depth_below_land, [0.1, 0.4])
    assert ds.depth_below_land.attrs["units"] == "m"
    wind = change(q, parameter="synthetic.u", level=500)
    source, _, _ = factory([q, wind], [q, wind])
    fields = source.sel([q, wind]).all(completeness="required")
    ds = fields.to_xarray()
    np.testing.assert_array_equal(ds.pressure, [850, 500])
    assert np.isnan(ds.t.isel(pressure=1)).all()
    assert np.isnan(ds.u.isel(pressure=0)).all()
    assert fields.report.overall["expected_count"] == 2


def test_mixed_layer_boundaries_and_time_representation_limit(factory, q):
    layer = Query(
        parameter="synthetic.st",
        layer={
            "bottom": {"type": "surface"},
            "top": {"type": "height_above_ground", "value": 3, "unit": "km"},
        },
    )
    source, _, _ = factory([layer], [layer])
    ds = source.sel(layer).to_xarray()
    name = "st__layer__bottom_surface__top_height_above_ground_3000m"
    assert (
        ds[name].attrs["layer_top_value"] == 3000
        and ds[name].attrs["layer_top_unit"] == "m"
    )
    assert "layer_bottom_value" not in ds[name].attrs
    far = change(q, time="2500-01-01T00:00:00Z")
    source, backend, _ = factory([far], [far])
    with pytest.raises(QueryError) as exc:
        source.sel(far).to_xarray()
    assert exc.value.code == "unsupported" and backend.loads == 0


def test_file_snapshot_guard_covers_lazy_materialization(tmp_path):
    from reki.selection.files import FileSnapshot

    path = tmp_path / "SYNTHETIC"
    path.write_bytes(b"before")
    snapshot = FileSnapshot.capture(path)

    class LazyValues:
        def load(self):
            path.write_bytes(b"changed during materialization")
            return b"loaded"

    with pytest.raises(SourceError) as exc:
        snapshot.load(LazyValues)
    assert exc.value.context["reason"] == "resource_changed"


def test_expected_member_role_is_canonical_and_cannot_create_false_missing(factory, q):
    with_role = change(q, member=0, member_role="control")
    without_role = change(q, member=0)
    source, backend, _ = factory(
        [with_role],
        [with_role, without_role],
        context={"member_roles": {"0": "control"}},
    )
    base_plan = backend.plan

    def independent(queries, config):
        p = base_plan(queries, config)
        return Plan(p.translations, ((with_role.to_dict(), without_role.to_dict()),))

    backend.plan = independent
    result = source.sel(with_role).all(completeness="required")
    assert result.report.overall["expected_count"] == 1
    original = backend.plan

    def bad_plan(queries, config):
        plan = original(queries, config)
        return Plan(
            plan.translations,
            ((change(q, member=0, member_role="perturbation").to_dict(),),),
        )

    backend.plan = bad_plan
    with pytest.raises(QueryError) as exc:
        source.sel(with_role)
    assert exc.value.code == "invalid_config" and exc.value.path.startswith(
        "/expected/0/"
    )


def test_chained_expansion_limit_counts_only_effective_combinations(factory, q):
    source, _, _ = factory([q], [q], context={"execution": {"max_expansion": 1}})
    selected = source.sel(q).sel(level_type="pressure", level=[850, 700, 500])
    assert selected.explain().analysis["expansion_count"] == 1
    assert selected.one().identity.level == 850


def test_large_member_role_conflict_cannot_hide_behind_an_empty_selection(factory, q):
    from dataclasses import replace
    from reki.selection.core import construct_source

    source, backend, _ = factory(
        [],
        None,
        context={"execution": {"max_expansion": 1}, "member_roles": {"2": "control"}},
    )
    config = replace(source.configuration, cemc_member_roles=True)
    source = construct_source(config, backend)
    empty = source.sel(q).sel(level_type="pressure", level=500)
    with pytest.raises(QueryError) as exc:
        empty.sel(
            member={"range": {"start": 1, "end": 1000000000, "every": 1}},
            member_role="control",
        )
    assert exc.value.code == "constraint_conflict"
    assert exc.value.path == "/queries/0/member_role"


def test_joint_limit_error_preserves_origins_across_selection_steps(factory):
    source, _, _ = factory([], None, context={"execution": {"max_expansion": 3}})
    selected = source.sel(parameter="t", level_type="pressure", level=[850, 500])
    with pytest.raises(QueryError) as exc:
        selected.sel(step=["PT6H", "PT12H"])
    assert exc.value.code == "expansion_limit_exceeded"
    assert thaw(exc.value.context["origins"]) == [
        dict(step_index=0, query_index=0),
        dict(step_index=1, query_index=0),
    ]


def test_dynamic_unknown_expectation_can_refine_to_independent_known_domain(factory, q):
    source, backend, refs = factory([q], None)
    lower = change(q, level=500)
    domain = [q, lower]

    def refine(plan):
        expected = expected_from_domain(
            backend.queries,
            domain,
            source.configuration,
            identity_fields=("parameter", "level_type", "level", "time", "step"),
        )
        return Plan(plan.translations, expected)

    scripted(backend, lambda plan: refs, refine=refine)
    selected = source.sel(change(q, level=[850, 500]))
    assert selected.explain().analysis["expected_count"] is None
    with pytest.raises(CompletenessError) as exc:
        selected.all(completeness="required")
    assert exc.value.report.overall["expected_count"] == 2
    assert exc.value.report.overall["missing"][0]["selection"]["level"] == 500


def test_branch_reference_indexes_are_strict_integers(factory, q):
    _, _, refs = factory([q], [q])
    for branches in (((True, 0),), ((0, -1),), ((0, 0, 1),)):
        with pytest.raises(QueryError) as exc:
            replace(refs[0], branches=branches)
        assert exc.value.code == "invalid_config"
