"""T08 explicit catalog snapshots and source-neutral Binding plans."""

import hashlib
import json
from pathlib import Path

import pytest

from cedarkit_query import AliasSnapshot, Binding, QueryError, binding_identity, query_identity
from reki.catalog import Catalog, CatalogError, load_catalog
from reki.catalog.query_binding import CatalogSnapshot, builtin_catalog_snapshot, plan_source_binding


def _query(dataset, parameter="cedarkit.t"):
    return {"api_version": "cedarkit.query/v1", "domain": "grid", "dataset": dataset,
            "parameter": parameter, "reference_time": "2026-08-30T00:00:00Z", "lead_time": "PT24H",
            "vertical": {"type": "surface"}, "statistic": {"kind": "instant"}}


def _document(*entries):
    return {"api_version": "reki.catalog/v1", "datasets": list(entries)}


def _snapshot(*entries, version="fixture-v1"):
    return CatalogSnapshot(load_catalog(builtin=False, plugins=False, user=False,
                                        explicit=_document(*entries)), version)


def _entry(dataset="grid", aliases=(), source=None):
    return {"id": dataset, "aliases": list(aliases),
            "source": source or {"name": "cmadaas", "kwargs": {"kind": "model_grid", "data_code": "DATA"}}}


def test_builtin_snapshot_hash_and_distinct_local_remote_datasets():
    snapshot = builtin_catalog_snapshot()
    expected = hashlib.sha256(Path(__file__).parents[2].joinpath(
        "src/reki/catalog/builtin/catalog.yaml").read_bytes()).hexdigest()
    assert snapshot.version == f"sha256:{expected}"
    remote = plan_source_binding(_query("cma_gfs_gmf_cmadaas"), snapshot=snapshot)
    assert remote.binding.kind == "cmadaas"
    assert remote.binding.dataset == "cma_gfs_gmf_cmadaas"
    assert remote.binding.data_code == "NAFP_FOR_FTM_GRAPES_GFS_25KM_GLB"
    assert remote.binding.request_kind == "model_grid"
    assert remote.binding.origin == "builtin"
    local = plan_source_binding(_query("cma_gfs_gmf"), snapshot=snapshot, local_config_version="config-1")
    assert local.binding.kind == "local"
    assert local.binding.locator["resolver"] == "reki-local"
    assert local.binding.locator["data_type"] == "cma_gfs_gmf/grib2/orig"
    assert local.binding.dataset != remote.binding.dataset
    assert local.query_id != remote.query_id


def test_catalog_alias_requires_explicit_namespace_and_resolves_to_stable_id():
    snapshot = builtin_catalog_snapshot()
    stable = plan_source_binding(_query("cma_gfs_gmf_cmadaas"), snapshot=snapshot)
    alias = plan_source_binding(_query({"namespace": "reki-catalog", "name": "CMA-GFS-CMADaaS"}),
                                snapshot=snapshot)
    assert stable.query == alias.query
    assert stable.query_id == alias.query_id
    assert stable.binding_id == alias.binding_id
    with pytest.raises(QueryError) as caught:
        plan_source_binding(_query("CMA-GFS-CMADaaS"), snapshot=snapshot)
    assert (caught.value.code, caught.value.path) == ("unknown_dataset", "/query/dataset")
    with pytest.raises(QueryError) as caught:
        plan_source_binding(_query({"namespace": "reki-catalog", "name": "missing"}), snapshot=snapshot)
    assert (caught.value.code, caught.value.path) == ("unknown_dataset", "/query/dataset")


def test_override_keeps_catalog_precedence_and_diagnostic():
    replacement = _entry("cma_gfs_gmf_cmadaas", aliases=["PRIVATE-GFS"],
                         source={"name": "cmadaas", "kwargs": {"kind": "model_grid", "data_code": "PRIVATE"}})
    catalog = load_catalog(plugins=False, user=False, explicit=_document(replacement))
    snapshot = CatalogSnapshot(catalog, "catalog-override-1")
    plan = plan_source_binding(_query({"namespace": "reki-catalog", "name": "PRIVATE-GFS"}), snapshot=snapshot)
    assert plan.binding.data_code == "PRIVATE"
    assert plan.origin == "explicit"
    assert plan.replaced_origins == ("builtin",)
    with pytest.raises(QueryError) as caught:
        plan_source_binding(_query({"namespace": "reki-catalog", "name": "CMA-GFS-CMADaaS"}), snapshot=snapshot)
    assert caught.value.code == "unknown_dataset"


def test_alias_conflicts_remain_catalog_errors():
    with pytest.raises(CatalogError, match="duplicate dataset alias"):
        load_catalog(builtin=False, plugins=False, user=False, explicit=_document(
            _entry("a", aliases=["shared"]), _entry("b", aliases=["shared"])))
    with pytest.raises(CatalogError, match="alias conflicts with active dataset"):
        load_catalog(plugins=False, user=False, explicit=_document(
            _entry("another", aliases=["CMA-GFS"])))


def test_same_query_rebound_to_new_root_changes_binding_only():
    first = _snapshot(_entry(source={"name": "file-pattern", "args": ["/mnt/old", "field.{forecast_hour_label}.grb2"]}),
                      version="catalog-1")
    second = _snapshot(_entry(source={"name": "file-pattern", "args": ["/mnt/new", "field.{forecast_hour_label}.grb2"]}),
                       version="catalog-2")
    old = plan_source_binding(_query("grid"), snapshot=first)
    new = plan_source_binding(_query("grid"), snapshot=second)
    assert old.query_id == new.query_id == query_identity(old.query)
    assert old.binding_id != new.binding_id
    assert old.binding_id == binding_identity(old.binding)
    assert old.binding.locator["root"] == "/mnt/old"
    assert new.binding.locator["root"] == "/mnt/new"
    assert "root" not in json.dumps(old.to_display_dict())
    assert "/mnt/old" not in json.dumps(old.to_display_dict())
    with pytest.raises(QueryError):
        Binding(old.to_display_dict())


def test_remote_data_code_is_a_binding_property_not_a_parameter_alias():
    first = _snapshot(_entry(), version="catalog-1")
    second = _snapshot(_entry(source={"name": "cmadaas", "kwargs": {
        "kind": "model_grid", "data_code": "OTHER_PRODUCT"}}), version="catalog-2")
    old = plan_source_binding(_query("grid"), snapshot=first)
    new = plan_source_binding(_query("grid"), snapshot=second)
    assert old.query_id == new.query_id
    assert old.binding_id != new.binding_id
    assert old.query.parameter == new.query.parameter == "cedarkit.t"
    assert "data_code" not in old.query.to_dict()


def test_parameter_alias_uses_only_explicit_vocabulary_snapshot():
    snapshot = _snapshot(_entry())
    stable = plan_source_binding(_query("grid"), snapshot=snapshot)
    alias = _query("grid", {"namespace": "test-vocabulary", "name": "temperature"})
    vocabulary = AliasSnapshot("vocab-1", {"test-vocabulary": {"temperature": "cedarkit.t"}})
    resolved = plan_source_binding(alias, snapshot=snapshot, vocabulary_snapshot=vocabulary)
    assert resolved.query_id == stable.query_id
    with pytest.raises(QueryError) as caught:
        plan_source_binding(alias, snapshot=snapshot)
    assert (caught.value.code, caught.value.path) == ("unknown_parameter", "/query/parameter")


def test_local_configuration_version_is_required_and_part_of_binding_identity():
    snapshot = builtin_catalog_snapshot()
    with pytest.raises(QueryError) as caught:
        plan_source_binding(_query("cma_gfs_gmf"), snapshot=snapshot)
    assert (caught.value.code, caught.value.path) == ("unsupported", "/binding/locator/config_version")
    first = plan_source_binding(_query("cma_gfs_gmf"), snapshot=snapshot, local_config_version="config-1")
    second = plan_source_binding(_query("cma_gfs_gmf"), snapshot=snapshot, local_config_version="config-2")
    assert first.query_id == second.query_id
    assert first.binding_id != second.binding_id


@pytest.mark.parametrize("source", [
    {"name": "memory"},
    {"name": "cmadaas", "kwargs": {"kind": "model_grid", "data_code": "DATA", "token": "secret"}},
    {"name": "cmadaas", "kwargs": {"kind": "other", "data_code": "DATA"}},
    {"name": "local", "args": ["data/type"], "kwargs": {"config_dir": "/private"}},
    {"name": "local", "args": ["../private"]},
    {"name": "file-pattern", "args": ["/mnt/{unsafe}", "file.grb2"]},
])
def test_unmapped_source_arguments_or_templates_fail_closed(source):
    snapshot = _snapshot(_entry(source=source))
    with pytest.raises(QueryError) as caught:
        plan_source_binding(_query("grid"), snapshot=snapshot, local_config_version="config-1")
    assert caught.value.code == "unsupported"
    assert "secret" not in str(caught.value)
    assert "/private" not in str(caught.value)


def test_display_redacts_user_origin_and_never_claims_availability():
    original = _snapshot(_entry(source={"name": "file-pattern", "args": ["/secret/root", "f.grb2"]}))
    snapshot = CatalogSnapshot(Catalog(original.catalog.records, {"grid": "user:/secret/catalog.yaml"}), "fixture-v1")
    plan = plan_source_binding(_query("grid"), snapshot=snapshot)
    display = plan.to_display_dict()
    assert display["locator_redacted"] is True
    assert display["origin"] == "user"
    assert "availability" not in display and "resource" not in display
    assert "/secret/root" not in json.dumps(display)
    assert "/secret/catalog.yaml" not in json.dumps(display)
    assert plan.binding.locator["root"] == "/secret/root"
