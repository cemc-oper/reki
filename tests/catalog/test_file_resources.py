"""Bind plain file queries to an independent, pinned GRIB2 resource pair."""

import json

import pytest
from cedarkit_query import QueryError, validate_standalone_grib2

from reki.catalog import load_resource, loader, plan_source_binding
from reki.catalog.model import thaw


def test_bundled_standalone_resources_pass_full_validation(tmp_path, monkeypatch):
    original = loader._read

    def read_file_resource(path, pointer):
        assert path.name in {"public-parameters.json", "generic-grib2-mappings.json"}
        return original(path, pointer)

    monkeypatch.setattr(loader, "_read", read_file_resource)
    source = {"kind": "file", "path": str(tmp_path / "forecast.grib2")}
    plan = plan_source_binding(source)
    assert plan.product is None
    assert plan.member_numbering is None
    assert [(row["role"], row["id"], row["version"]) for row in plan.definitions] == [
        ("parameter_registry", "cedarkit.parameters.public", "3"),
        ("mappings", "cedarkit.grib2.generic", "5"),
    ]
    parameters, mappings = (
        load_resource(row["reference"], kind)
        for row, kind in zip(plan.definitions, ("parameters", "mappings"))
    )
    assert parameters.snapshot("parameter_registry") == thaw(plan.definitions[0])
    assert mappings.snapshot("mappings", backend="grib2") == thaw(plan.definitions[1])
    assert all(row["sha256"] == row["reference"]["sha256"] for row in plan.definitions)
    assert validate_standalone_grib2(parameters.value, mappings.value) == thaw(plan.parameters)
    assert plan.origins["parameter_registry"] == plan.origins["mappings.grib2"] == "builtin"


def test_plain_file_can_replay_an_explicit_independent_pair(tmp_path):
    source = {"kind": "file", "path": str(tmp_path / "forecast.grib2")}
    context_path = tmp_path / "context.json"
    (tmp_path / "parameters.json").write_bytes(
        loader.BUILTINS["reki.parameters.public"].read_bytes()
    )
    mappings_path = tmp_path / "mappings.json"
    mappings_path.write_bytes(loader.BUILTINS["reki.mappings.grib2.generic"].read_bytes())
    context_path.write_text(json.dumps({
        "parameter_registry": {"path": "parameters.json"},
        "mappings": {"grib2": {"path": "mappings.json"}},
    }))
    plan = plan_source_binding(source, context=context_path)
    assert plan.parameters["cedarkit.t2m"]["unit"] == "K"
    assert plan.product is None
    assert plan.origins["parameter_registry"] == plan.origins["mappings.grib2"] == "context"

    scoped = json.loads(mappings_path.read_bytes())
    scoped["mappings"][0]["applies_to"]["dataset"] = "cma_gfs_gmf"
    mappings_path.write_text(json.dumps(scoped))
    with pytest.raises(QueryError) as caught:
        plan_source_binding(source, context=context_path)
    assert caught.value.code == "invalid_config"
    assert caught.value.path == "/mappings/0/applies_to"


def test_plain_file_rejects_modified_bundled_resource_bytes(tmp_path, monkeypatch):
    builtin = "reki.parameters.public"
    updated = tmp_path / "public-parameters.json"
    updated.write_bytes(loader.BUILTINS[builtin].read_bytes() + b"\n")
    monkeypatch.setattr(loader, "BUILTINS", {**loader.BUILTINS, builtin: updated})
    with pytest.raises(QueryError) as caught:
        plan_source_binding({"kind": "file", "path": str(tmp_path / "forecast.grib2")})
    assert (caught.value.code, caught.value.path) == (
        "invalid_config", "/context/parameter_registry/sha256"
    )
