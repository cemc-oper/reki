"""Task 03 snapshot binding without opening business data."""

import json
from copy import deepcopy

import pytest
from cedarkit_query import QueryError, Request, prepare_queries
from reki import from_source
from reki.catalog import load_resource, plan_source_binding
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
    assert all("step" not in q for q in plan.product["provides"])
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
        ("catalog", "34"),
        ("parameter_registry", "15"),
        ("mappings", "20"),
    ]
    assert all(len(row["sha256"]) == 64 for row in facts["definitions"])


def test_restore_pinned_snapshots_through_relative_paths(tmp_path):
    builtin = plan_source_binding(SOURCE)
    context_dir = tmp_path / "context"
    snapshot_dir = tmp_path / "snapshot"
    context_dir.mkdir()
    snapshot_dir.mkdir()
    references = {}
    for row in builtin.definitions:
        source = BUILTINS[row["reference"]["builtin"]]
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
    ref = {"builtin": row["reference"]["builtin"], field: bad}
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
        data["mappings"].remove(first)
    resource = tmp_path / "maps.json"
    resource.write_text(json.dumps(data))
    with pytest.raises(QueryError) as caught:
        plan_source_binding(
            SOURCE, context={"mappings": {"grib2": {"path": str(resource)}}}
        )
    assert caught.value.code == "invalid_config"
    assert path in caught.value.path


def test_catalog_relative_defaults_take_precedence_over_builtins(tmp_path):
    catalog = load_resource({"builtin": "reki.catalog"}, "catalog").value.to_dict()
    dataset = next(d for d in catalog["datasets"] if d["id"] == "cma_gfs_gmf")
    for ref in (dataset["parameter_registry"], dataset["mappings"]["grib2"]):
        path = BUILTINS[ref.pop("builtin")]
        ref["path"] = path.name
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
        assert {
            branch["residual"]["member_role"]
            for translation in analysis["translations"]
            for branch in translation["branches"]
        } == {"control", "perturbation"}
        with pytest.raises(QueryError, match="no reviewed GRIB mapping"):
            reader.sel(parameter="cedarkit.t2m", **TIME, member=last_member + 1)
