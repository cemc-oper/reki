import json
from copy import deepcopy

import pytest

from cedarkit_query import Query, QueryError, QueryExplanation, prepare_queries
from reki.catalog import plan_source_binding


def plan(resources, **kwargs):
    options = {
        "context": resources["context"],
        "product": "orig",
        "product_version": "test-1",
    }
    options.update(kwargs)
    return plan_source_binding(resources["source"], **options)


def test_exact_product_and_paired_provides_are_frozen(resources):
    p = plan(resources)
    assert p.source["dataset"] == "synthetic"
    assert p.product["provides"] == ({"parameter": "test.t2m"},)
    assert p.scope.to_dict() == {"step": "PT0S"}
    assert p.execution_defaults == {"completeness": "required", "max_expansion": 25}
    with pytest.raises(TypeError):
        p.product["version"] = "other"
    resources["source"]["path"] = "mutated"
    assert p.source["path"].endswith("SYNTHETIC*.grb")
    report = p.report_context()
    QueryExplanation(
        {
            "effective_queries": [],
            "context": report,
            "steps": [],
            "analysis": {
                "expansion_count": None,
                "expected_count": None,
                "checks": [],
                "translations": [],
            },
        }
    )
    report["definitions"].clear()
    assert len(p.definitions) == 3


def test_no_file_discovery_or_parameter_default_for_native_file(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("business discovery must wait for I05 execution")

    monkeypatch.setattr(type(tmp_path), "glob", forbidden)
    p = plan_source_binding(
        {"kind": "file", "directory": str(tmp_path), "glob": ["b*.grb", "a*.grb"]}
    )
    assert p.source["glob"] == ("b*.grb", "a*.grb")
    assert p.resources is None and p.product is None and p.scope == Query({})
    assert p.member_role(0) is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"product": None},
        {"product_version": None},
        {"product_version": "unknown"},
        {"product": "missing"},
        {"source_id": "absent"},
    ],
)
def test_missing_product_version_or_source_fails(resources, kwargs):
    with pytest.raises(QueryError) as error:
        plan(resources, **kwargs)
    assert error.value.code == "invalid_config"
    assert error.value.context["reason"] == "missing_context"


def test_conflicting_scope_and_fixed_parameter(resources):
    with pytest.raises(QueryError) as error:
        plan(resources, context={**resources["context"], "scope": {"step": "PT6H"}})
    assert error.value.code == "constraint_conflict"
    p = plan(resources)
    with pytest.raises(QueryError) as error:
        prepare_queries(
            [{"parameter": "t2m", "level_type": "height_above_ground", "level": 10}],
            p.resources,
        )
    assert error.value.code == "constraint_conflict"


def test_mapping_override_replaces_without_reading_lower_layer(resources):
    catalog = deepcopy(resources["catalog"])
    catalog["datasets"][0]["mappings"]["grib2"] = {"path": "not-there.json"}
    resources["write"]("catalog.json", catalog)
    replacement = deepcopy(resources["mappings"])
    replacement["id"] = "explicit.replacement"
    path = resources["write"]("replacement.json", replacement)
    p = plan(
        resources,
        context={**resources["context"], "mappings": {"grib2": {"path": path}}},
    )
    assert len(p.resources.mappings) == 1
    assert p.resources.mappings[0]["id"] == "explicit.replacement"
    assert p.origins["mappings.grib2"] == "context"


def test_replacement_does_not_excuse_absent_parameter(resources):
    mappings = deepcopy(resources["mappings"])
    mappings["mappings"][0]["parameter_id"] = "absent"
    path = resources["write"]("bad.json", mappings)
    with pytest.raises(QueryError):
        plan(
            resources,
            context={**resources["context"], "mappings": {"grib2": {"path": path}}},
        )


def test_roles_override_per_member_and_execution_per_field(resources):
    p = plan(
        resources,
        context={
            **resources["context"],
            "member_roles": {"0": "control"},
            "execution": {"max_expansion": 10},
        },
    )
    assert (
        p.member_role(0) == "control"
        and p.member_role(2) == "control"
        and p.member_role(1) is None
    )
    assert p.execution_defaults == {"max_expansion": 10, "completeness": "required"}
    assert p.origins["execution.completeness"] == "dataset"


def test_ambiguous_binding_requires_explicit_id(resources):
    catalog = deepcopy(resources["catalog"])
    catalog["datasets"][0]["products"][0]["sources"].append(
        {"id": "other-files", "kind": "file"}
    )
    resources["write"]("catalog.json", catalog)
    with pytest.raises(QueryError):
        plan(resources)
    assert (
        plan(resources, source_id="other-files").origins["source_binding"]
        == "other-files"
    )


def test_local_layout_order_and_root_are_kept_without_scan(resources):
    source = {"kind": "local", "dataset": "alias", "root": "/SYNTHETIC"}
    key = ("synthetic", "orig", "test-1", "local")
    p = plan_source_binding(
        source,
        context=resources["context"],
        product="orig",
        product_version="test-1",
        local_layouts={
            key: ["primary/{start_time_label}/{forecast_hour}.grb", "secondary/f.grb"]
        },
    )
    assert p.layout[0].startswith("primary/") and p.source["root"] == "/SYNTHETIC"
    with pytest.raises(QueryError):
        plan_source_binding(
            source,
            context=resources["context"],
            product="orig",
            product_version="test-1",
        )


@pytest.mark.parametrize(
    "template",
    [
        "../bad",
        "/absolute",
        "x/{unknown}",
        "x/{forecast_hour!r}",
        "x/{forecast_hour:02}",
    ],
)
def test_bad_local_templates(resources, template):
    with pytest.raises(QueryError):
        plan_source_binding(
            {"kind": "local", "dataset": "alias", "root": "/SYNTHETIC"},
            context=resources["context"],
            product="orig",
            product_version="test-1",
            local_layouts={("synthetic", "orig", "test-1", "local"): [template]},
        )


def test_cmadaas_exact_registry_and_credential_redaction(resources):
    source = {
        "kind": "cmadaas",
        "dataset": "alias",
        "config": "/secret/connection.yaml",
    }
    options = {
        "context": resources["context"],
        "product": "orig",
        "product_version": "test-1",
    }
    with pytest.raises(QueryError, match="not registered"):
        plan_source_binding(source, **options)
    p = plan_source_binding(
        source, **options, interface_contracts={("synthetic.grid", 1)}
    )
    assert p.product["sources"][2]["time_zone"] == "Asia/Shanghai"
    report = p.report_context()
    assert report["source"]["data_code"] == "SYNTHETIC"
    assert "secret" not in json.dumps(report) and "config" not in report["source"]
    with pytest.raises(QueryError, match="conflicts"):
        plan_source_binding(source, **options, client=object())
    source.pop("config")
    with pytest.raises(QueryError, match="needs config"):
        plan_source_binding(source, **options)
    assert (
        plan_source_binding(
            source,
            **options,
            client=object(),
            interface_contracts={("synthetic.grid", 1)},
        ).source["kind"]
        == "cmadaas"
    )


def test_missing_population_gets_shared_diagnostic(resources):
    parameters = deepcopy(resources["parameters"])
    parameters["parameters"].append(
        {
            "parameter_id": "test.prob",
            "name": "prob",
            "unit": "%",
            "fixed_conditions": {
                "statistics": {
                    "over": "ensemble",
                    "operation": "probability",
                    "of": {"parameter_id": "test.t"},
                    "population": {"ref": "all"},
                    "event": {
                        "operator": "ge",
                        "threshold": {"value": 280, "unit": "K"},
                    },
                    "method": {
                        "kind": "member_fraction",
                        "denominator": "expected_members",
                    },
                }
            },
        }
    )
    resources["write"]("parameters.json", parameters)
    catalog = deepcopy(resources["catalog"])
    catalog["datasets"][0]["products"][0]["provides"] = [{"parameter": "test.prob"}]
    resources["write"]("catalog.json", catalog)
    with pytest.raises(QueryError, match="population"):
        plan(resources)


def test_ambiguous_parameter_names_are_not_guessed(resources):
    parameters = deepcopy(resources["parameters"])
    parameters["parameters"].extend(
        [
            {"parameter_id": "test.a", "name": "ambiguous", "unit": "K"},
            {"parameter_id": "test.b", "name": "ambiguous", "unit": "K"},
        ]
    )
    resources["write"]("parameters.json", parameters)
    catalog = deepcopy(resources["catalog"])
    catalog["datasets"][0]["products"][0]["provides"] = [{"parameter": "ambiguous"}]
    resources["write"]("catalog.json", catalog)
    with pytest.raises(QueryError) as error:
        plan(resources)
    assert error.value.context["reason"] == "ambiguous_parameter"


def test_cemc_member_defaults_require_registered_dataset_identity(resources):
    catalog = deepcopy(resources["catalog"])
    catalog["datasets"][0]["id"] = "cma_geps"
    resources["write"]("catalog.json", catalog)
    mappings = deepcopy(resources["mappings"])
    mappings["mappings"][0]["applies_to"]["dataset"] = "cma_geps"
    resources["write"]("maps.json", mappings)
    p = plan(resources)
    assert p.source["dataset"] == "cma_geps"
    assert p.member_role(0) == "perturbation"  # explicit dataset override
    assert p.member_role(1) == "perturbation" and p.member_role(2) == "control"


def test_source_invalid_combinations_are_shared_contract(resources):
    for source in [
        {"kind": "file", "path": "a", "directory": "b", "glob": "*"},
        {"kind": "local", "root": "/a"},
        {"kind": "cmadaas"},
        {"kind": "file", "path": "a", "data_code": "override"},
    ]:
        with pytest.raises(QueryError):
            plan_source_binding(source)


def test_bad_explicit_resource_does_not_read_registered_default(resources):
    with pytest.raises(QueryError, match="unknown builtin"):
        plan_source_binding(
            {"kind": "file", "path": "f"},
            context={"catalog": {"builtin": "unknown"}},
            defaults=resources["context"],
        )


def test_relative_request_context_and_catalog_mapping_bases(
    resources, tmp_path, monkeypatch
):
    config = tmp_path / "config"
    config.mkdir()
    (config / "context.yaml").write_text(
        "catalog: {path: ../catalog.json}\nparameter_registry: {path: ../parameters.json}\n"
    )
    from cedarkit_query import Request

    request = Request.from_dict(
        {
            "api_version": "cedarkit.request/v1",
            "source": resources["source"],
            "context": "config/context.yaml",
            "queries": [{}],
        },
        base_dir=tmp_path,
    )
    monkeypatch.chdir(config)
    p = plan_source_binding(
        request.source,
        context=request.context,
        product="orig",
        product_version="test-1",
    )
    assert p.definitions[-1]["reference"]["path"] == str(tmp_path / "maps.json")


def test_mapping_replacement_must_apply_to_exact_business_version(resources):
    replacement = deepcopy(resources["mappings"])
    replacement["mappings"][0]["applies_to"]["product_version"] = "other-version"
    path = resources["write"]("wrong-product.json", replacement)
    with pytest.raises(QueryError, match="does not cover declared product"):
        plan(
            resources,
            context={**resources["context"], "mappings": {"grib2": {"path": path}}},
        )
    p = plan(resources)
    assert p.mapping_applicability[0]["product_context_matches"] is True
    assert p.mapping_applicability[0]["translation_coverage"] == "pending_I06"


def test_context_and_product_scopes_conjoin_without_replacing_or_defaulting(resources):
    p = plan(
        resources, context={**resources["context"], "scope": {"step": ["PT0H", "PT6H"]}}
    )
    assert p.scope.to_dict() == {"step": "PT0S"}
    assert p.product["provides"] == ({"parameter": "test.t2m"},)
    assert "step" not in resources["context"].get("scope", {})


def test_fixed_member_role_uses_effective_overrides(resources):
    parameters = deepcopy(resources["parameters"])
    parameters["parameters"].append(
        {
            "parameter_id": "test.control",
            "name": "control",
            "unit": "K",
            "fixed_conditions": {"member": 0, "member_role": "control"},
        }
    )
    resources["write"]("parameters.json", parameters)
    catalog = deepcopy(resources["catalog"])
    catalog["datasets"][0]["products"][0]["provides"] = [{"parameter": "test.control"}]
    resources["write"]("catalog.json", catalog)
    mappings = deepcopy(resources["mappings"])
    mappings["mappings"][0]["parameter_id"] = "test.control"
    resources["write"]("maps.json", mappings)
    with pytest.raises(QueryError) as error:
        plan(resources)
    assert error.value.code == "constraint_conflict"
    p = plan(
        resources, context={**resources["context"], "member_roles": {"0": "control"}}
    )
    assert p.member_role(0) == "control"


def test_catalog_scope_is_a_bound_not_an_expanded_request(resources):
    catalog = deepcopy(resources["catalog"])
    catalog["datasets"][0]["products"][0]["scope"]["member"] = {
        "range": {"start": 0, "end": 1000000000, "every": 1}
    }
    resources["write"]("catalog.json", catalog)
    p = plan(resources)
    assert p.scope.member["range"]["end"] == 1000000000
    assert p.execution_defaults["max_expansion"] == 25


def test_registered_layout_can_describe_existing_mount_and_member_declarations(
    resources,
):
    key = ("synthetic", "orig", "test-1", "local")
    template = "{year}/{date_label}/Z_{start_time_label}_{forecast_hour_label}_m{member_3digit}.grib2"
    p = plan_source_binding(
        {"kind": "local", "dataset": "alias", "root": "/SYNTHETIC"},
        context=resources["context"],
        product="orig",
        product_version="test-1",
        local_layouts={key: [template]},
    )
    assert p.layout == (template,)


def test_explicit_replacement_cannot_ignore_mapping_time_or_when(resources):
    mappings = deepcopy(resources["mappings"])
    mappings["mappings"][0]["when"] = {"step": "PT6H"}
    resources["write"]("maps.json", mappings)
    with pytest.raises(QueryError) as error:
        plan(resources)
    assert error.value.context["provided_index"] == 0
    assert error.value.context["static_status"] == "missing"


def test_static_coverage_is_retained_without_claiming_translation(resources):
    p = plan(resources)
    assert p.product_coverage[0]["static_status"] == "covered"
    assert p.product_coverage[0]["translation_coverage"] == "pending_I06"
    with pytest.raises(TypeError):
        p.product_coverage[0]["static_status"] = "passed"
