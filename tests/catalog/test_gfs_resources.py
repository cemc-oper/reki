"""Task 03 snapshot binding without opening business data."""

import json
from copy import deepcopy

import pytest
from cedarkit_query import QueryError, Request, prepare_queries, validate_resource_set
from cedarkit_query.resources import effective_parameters
from reki import from_source
from reki.catalog import load_resource, loader, plan_source_binding, query_binding
from reki.catalog._cache import _ResourceCache
from reki.catalog.loader import BUILTINS

SOURCE = {"kind": "local", "dataset": "CMA-GFS", "root": "/CMADAAS"}
TIME = {"time": "2026-11-02T12:00:00Z", "step": "PT6H"}
QUERIES = [
    {"parameter": "cedarkit.t2m", **TIME},
    {
        "parameter": "cedarkit.t",
        "level_type": "pressure",
        "level": 850,
        "level_unit": "hPa",
        **TIME,
    },
]


def test_load_resource_reuses_identical_content_per_format(tmp_path):
    text = (
        "api_version: cedarkit.catalog/v1\n"
        "id: test.catalog\n"
        "version: '1'\n"
        "datasets: [{id: test}]\n"
    )
    original = tmp_path / "catalog.yaml"
    original.write_text(text)
    nested = tmp_path / "nested"
    nested.mkdir()
    copy = nested / "catalog.yml"
    copy.write_text(text)

    first = load_resource({"path": str(original)}, "catalog")
    second = load_resource({"path": str(copy)}, "catalog")
    assert second.value is first.value
    assert second.base_dir == nested
    assert second.reference["path"] == str(copy)

    json_path = tmp_path / "catalog.json"
    json_path.write_text(text)
    with pytest.raises(QueryError):
        load_resource({"path": str(json_path)}, "catalog")

    original.write_text(text.replace("test.catalog", "updated.catalog"))
    updated = load_resource({"path": str(original)}, "catalog")
    assert updated.value.id == "updated.catalog"
    assert updated.sha256 != first.sha256


def test_default_catalog_resource_combinations_pass_cross_validation():
    def load_and_compare(reference, kind, *, base_dir=None):
        checked = load_resource(reference, kind, base_dir=base_dir)
        prevalidated = loader._load_resource(
            reference, kind, base_dir=base_dir, prevalidated=True
        )
        assert prevalidated == checked
        return checked

    catalog = load_and_compare({"builtin": "reki.catalog"}, "catalog")
    for dataset in catalog.value.datasets:
        if not dataset.get("products"):
            continue
        parameters = load_and_compare(
            dataset["parameter_registry"], "parameters", base_dir=catalog.base_dir
        ).value
        mappings = tuple(
            load_and_compare(ref, "mappings", base_dir=catalog.base_dir).value
            for ref in dataset.get("mappings", {}).values()
        )
        validated = validate_resource_set(
            parameters, mappings, catalog.value, dataset["id"]
        )
        assert validated == effective_parameters(parameters), dataset["id"]


@pytest.mark.parametrize("role", ["catalog", "parameter_registry", "mappings"])
def test_default_binding_cache_validates_explicit_resources(monkeypatch, role):
    seen = []
    checked = []
    prevalidated = []
    validate = query_binding.validate_resource_set
    load_checked = loader.load_value
    load_prevalidated = loader.load_prevalidated_resource

    def record_validation(parameters, mappings, catalog, dataset_id):
        seen.append(dataset_id)
        return validate(parameters, mappings, catalog, dataset_id)

    def record_checked(text, kind, **kwargs):
        checked.append(kind)
        return load_checked(text, kind, **kwargs)

    def record_prevalidated(text, kind):
        prevalidated.append(kind)
        if load_prevalidated is not None:
            return load_prevalidated(text, kind)
        return load_checked(text, kind, format="json")

    monkeypatch.setattr(query_binding, "_VALIDATED_BINDINGS", _ResourceCache(maxsize=2))
    monkeypatch.setattr(query_binding, "validate_resource_set", record_validation)
    monkeypatch.setattr(loader, "_PARSED_RESOURCES", _ResourceCache(maxsize=6))
    monkeypatch.setattr(loader, "load_value", record_checked)
    monkeypatch.setattr(loader, "load_prevalidated_resource", record_prevalidated)
    default = plan_source_binding(SOURCE)
    repeated = plan_source_binding(SOURCE, context={"execution": {"max_expansion": 5}})
    assert repeated.parameters is default.parameters
    assert not seen
    assert prevalidated == ["catalog", "parameters", "mappings"]
    assert not checked

    row = next(row for row in default.definitions if row["role"] == role)
    ref = dict(row["reference"])
    if role == "catalog":
        ref["path"] = str(BUILTINS[ref.pop("builtin")])
    context = {role: {"grib2": ref} if role == "mappings" else ref}
    explicit = plan_source_binding(SOURCE, context=context)
    assert seen == [default.source["dataset"]]
    assert explicit.parameters == default.parameters
    assert checked == {
        "catalog": ["catalog", "parameters", "mappings"],
        "parameter_registry": ["parameters"],
        "mappings": ["mappings"],
    }[role]


def test_bindings_cache_resource_validation_per_dataset(monkeypatch):
    seen = []
    validate = query_binding.validate_resource_set

    def record_validation(parameters, mappings, catalog, dataset_id):
        seen.append(dataset_id)
        return validate(parameters, mappings, catalog, dataset_id)

    monkeypatch.setattr(query_binding, "_VALIDATED_BINDINGS", _ResourceCache(maxsize=2))
    monkeypatch.setattr(query_binding, "validate_resource_set", record_validation)
    context = {"catalog": {"builtin": "reki.catalog.cmadaas.task07a"}}
    analysis = {"kind": "cmadaas", "dataset": "cma_gfs_gmf_analysis_cmadaas"}
    forecast = {"kind": "cmadaas", "dataset": "cma_gfs_gmf_cmadaas"}

    first = plan_source_binding(analysis, context=context, client=object())
    repeated = plan_source_binding(
        analysis,
        context={**context, "execution": {"max_expansion": 5}},
        client=object(),
    )
    other = plan_source_binding(forecast, context=context, client=object())

    assert seen == [analysis["dataset"], forecast["dataset"]]
    assert repeated.parameters is first.parameters
    assert repeated.execution_defaults["max_expansion"] == 5
    assert first.execution_defaults["max_expansion"] != 5
    assert other.product["id"] == "forecast"


def test_packaged_gfs_snapshots_bind_frozen_requests(tmp_path):
    request = Request.from_dict(
        {
            "api_version": "cedarkit.request/v1",
            "source": {**SOURCE, "root": str(tmp_path)},
            "queries": QUERIES,
        }
    )
    plan = plan_source_binding(request.source, context=request.context)
    assert (plan.product["id"], plan.product["version"]) == ("orig", "current")
    assert plan.layout[0].endswith("-{forecast_hour_label}00.grib2")
    assert plan.parameters["cedarkit.t2m"]["unit"] == "K"
    assert {"cedarkit.t", "cedarkit.t2m"} <= plan.parameters.keys()
    expected = prepare_queries(plan.product["expected_domain"], plan.parameters)
    actual = prepare_queries(request.queries, plan.parameters)
    assert actual == expected
    by_id = {q.parameter: q for q in actual}
    assert by_id["cedarkit.t2m"].level == 2
    assert by_id["cedarkit.t"].level == 850
    assert all(q.valid_time == "2026-11-02T18:00:00Z" for q in actual)
    rows = {m["parameter_id"]: m for m in plan.mappings[0].to_dict()["mappings"]}
    assert rows["cedarkit.t"]["native"]["match"]["typeOfFirstFixedSurface"] == 100
    assert rows["cedarkit.t2m"]["native"]["match"]["typeOfFirstFixedSurface"] == 103
    radiation_ids = {"cedarkit.gusw", "cedarkit.tusw", "cedarkit.gulw", "cedarkit.tulw"}
    radiation = [q for q in plan.product["provides"] if q["parameter"] in radiation_ids]
    assert {q["parameter"] for q in radiation} == radiation_ids
    assert all(q.keys() == {"parameter"} for q in radiation)
    assert all(
        "level" not in q
        for q in plan.product["provides"]
        if q["parameter"] == "cedarkit.t"
    )
    with from_source(request.source, context=request.context) as source:
        facts = (
            source.sel(native={"grib": {"shortName": "2t"}})
            .explain()
            .to_dict()["context"]
        )
    assert [(r["role"], r["version"]) for r in facts["definitions"]] == [
        ("catalog", "57"),
        ("parameter_registry", "20"),
        ("mappings", "25"),
    ]
    assert all(len(row["sha256"]) == 64 for row in facts["definitions"])


def test_restore_pinned_snapshots_through_relative_paths(tmp_path):
    builtin = plan_source_binding(SOURCE)
    context_dir = tmp_path / "context"
    snapshot_dir = tmp_path / "snapshot"
    context_dir.mkdir()
    snapshot_dir.mkdir()
    references = {}
    catalog_dir = BUILTINS["reki.catalog"].parent
    for row in builtin.definitions:
        reference = row["reference"]
        if "builtin" in reference:
            source = BUILTINS[reference["builtin"]]
        else:
            source = catalog_dir / reference["path"]
        (snapshot_dir / source.name).write_bytes(source.read_bytes())
        references[row["role"]] = {
            "path": f"../snapshot/{source.name}",
            "version": row["version"],
            "sha256": row["sha256"],
        }
    context = {
        "catalog": references["catalog"],
        "parameter_registry": references["parameter_registry"],
        "mappings": {"grib2": references["mappings"]},
        "scope": {"time": TIME["time"]},
        "execution": {"max_expansion": 10},
        "member_roles": {"1": "control"},
    }
    path = context_dir / "request-context.json"
    path.write_text(json.dumps(context))
    restored = plan_source_binding(SOURCE, context=path)
    assert restored.parameters == builtin.parameters
    assert restored.mappings == builtin.mappings
    assert restored.scope.time == TIME["time"]
    assert restored.execution_defaults["max_expansion"] == 10
    assert restored.member_role(1) == "control"
    assert restored.origins["mappings.grib2"] == "context"
    assert [row["sha256"] for row in restored.definitions] == [
        row["sha256"] for row in builtin.definitions
    ]


@pytest.mark.parametrize("role", ["catalog", "parameter_registry", "mappings"])
@pytest.mark.parametrize("field,bad", [("version", "999"), ("sha256", "0" * 64)])
def test_reject_resource_pins_without_fallback(role, field, bad):
    plan = plan_source_binding(SOURCE)
    row = next(row for row in plan.definitions if row["role"] == role)
    ref = dict(row["reference"])
    if "path" in ref:
        ref["path"] = str(BUILTINS["reki.catalog"].parent / ref["path"])
    ref[field] = bad
    context = {role: {"grib2": ref} if role == "mappings" else ref}
    with pytest.raises(QueryError) as caught:
        plan_source_binding(SOURCE, context=context)
    pointer = "mappings/grib2" if role == "mappings" else role
    assert (caught.value.code, caught.value.path) == (
        "invalid_config",
        f"/context/{pointer}/{field}",
    )


@pytest.mark.parametrize(
    "problem,path",
    [
        ("unknown_parameter", "/parameter_id"),
        ("wrong_product_version", "/applies_to"),
        ("duplicate_scope", "/native/match"),
        ("missing_mapping", "/provides/"),
    ],
)
def test_reject_incompatible_mappings(tmp_path, problem, path):
    plan = plan_source_binding(SOURCE)
    data = plan.mappings[0].to_dict()
    resource = tmp_path / "maps.json"
    context = {"mappings": {"grib2": {"path": str(resource)}}}
    resource.write_text(json.dumps(data))
    plan_source_binding(SOURCE, context=context)

    first = next(
        row for row in data["mappings"] if row["id"] == "t2m.operational.instantaneous"
    )
    if problem == "unknown_parameter":
        first["parameter_id"] = "unknown"
    elif problem == "wrong_product_version":
        first["applies_to"]["product_version"] = "wrong"
    elif problem == "duplicate_scope":
        duplicate = deepcopy(first)
        duplicate.update(id="duplicate", applies_to={})
        data["mappings"].append(duplicate)
    else:
        data["mappings"] = [
            row for row in data["mappings"] if row["parameter_id"] != first["parameter_id"]
        ]
    resource.write_text(json.dumps(data))
    with pytest.raises(QueryError) as caught:
        plan_source_binding(SOURCE, context=context)
    assert caught.value.code == "invalid_config"
    assert path in caught.value.path


def test_catalog_relative_defaults_take_precedence_over_builtins(tmp_path):
    catalog = load_resource({"builtin": "reki.catalog"}, "catalog").value.to_dict()
    dataset = next(d for d in catalog["datasets"] if d["id"] == "cma_gfs_gmf")
    catalog_dir = BUILTINS["reki.catalog"].parent
    for ref in (dataset["parameter_registry"], dataset["mappings"]["grib2"]):
        path = catalog_dir / ref["path"]
        (tmp_path / path.name).write_bytes(path.read_bytes())
    (tmp_path / "catalog.json").write_text(json.dumps(catalog))
    plan = plan_source_binding(
        SOURCE, context={"catalog": {"path": "catalog.json"}}, base_dir=tmp_path
    )
    assert plan.origins["parameter_registry"] == "dataset"
    assert plan.definitions[1]["reference"]["path"] == str(
        tmp_path / "current-gfs-parameters.json"
    )


@pytest.mark.parametrize("dataset,last_member", [("cma_geps", 30), ("cma_reps", 14)])
def test_reviewed_member_bounds_are_planned_without_discovery(
    tmp_path, dataset, last_member
):
    source = {"kind": "local", "dataset": dataset, "root": str(tmp_path)}
    with from_source(source) as reader:
        analysis = (
            reader.sel(
                parameter="cedarkit.t2m",
                **TIME,
                member={"range": {"start": 0, "end": last_member, "every": 1}},
            )
            .explain()
            .to_dict()["analysis"]
        )
        assert analysis["expansion_count"] == last_member + 1
        branches = [branch for translation in analysis["translations"] for branch in translation["branches"]]
        assert {
            branch["residual"]["member_role"] for branch in branches
            if "member_role" in branch["residual"]
        } == {"control", "perturbation"}
        assert {
            branch["candidate_filter"]["typeOfEnsembleForecast"]
            for branch in branches if "member_role" not in branch["residual"]
        } == {0, 2, 3}
        for member in (last_member + 1, [0, last_member + 1]):
            with pytest.raises(QueryError, match="no reviewed GRIB mapping"):
                reader.sel(parameter="cedarkit.t2m", **TIME, member=member)
