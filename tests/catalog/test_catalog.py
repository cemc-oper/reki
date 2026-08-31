import pytest

from reki.catalog import CatalogError, load_catalog


def document(*datasets):
    return {"api_version": "reki.catalog/v1", "datasets": list(datasets)}


def dataset(dataset_id="demo", aliases=(), **kwargs):
    return {"id": dataset_id, "aliases": list(aliases), "source": {
        "name": "memory", "kwargs": kwargs,
    }}


def test_resolve_is_pure_and_tracks_origin():
    catalog = load_catalog(builtin=False, plugins=False, user=False, explicit=document(dataset("demo", ["legacy"], token="secret")))
    resolved = catalog.resolve("legacy")
    assert resolved.record.dataset_id == "demo"
    assert resolved.source.kwargs["token"] == "secret"
    assert resolved.origin == "explicit"


def test_replacement_is_whole_record_and_diagnostic_is_preserved():
    catalog = load_catalog(builtin=False, plugins=False, user=False, explicit=document(dataset("demo", ["new"])))
    assert catalog.resolve("demo").record.aliases == ("new",)


def test_cmadaas_record_can_be_replaced_without_loading_the_client():
    override = {
        "id": "cma_gfs_gmf_cmadaas",
        "aliases": ["PRIVATE-CMA-GFS-CMADaaS"],
        "source": {
            "name": "cmadaas",
            "kwargs": {
                "kind": "model_grid",
                "data_code": "PRIVATE_PRODUCT_CODE",
            },
        },
        "metadata": {"provider": "cmadaas-remote"},
    }

    catalog = load_catalog(plugins=False, user=False, explicit=document(override))
    resolved = catalog.resolve("PRIVATE-CMA-GFS-CMADaaS")

    assert resolved.origin == "explicit"
    assert resolved.replaced_origins == ("builtin",)
    assert resolved.source.kwargs == {
        "kind": "model_grid",
        "data_code": "PRIVATE_PRODUCT_CODE",
    }
    with pytest.raises(KeyError):
        catalog.resolve("CMA-GFS-CMADaaS")


def test_unknown_fields_and_alias_conflicts_fail():
    with pytest.raises(CatalogError, match="unknown catalog fields"):
        load_catalog(builtin=False, plugins=False, user=False, explicit={"api_version": "reki.catalog/v1", "datasets": [], "extra": True})
    with pytest.raises(CatalogError, match="duplicate dataset alias"):
        load_catalog(builtin=False, plugins=False, user=False, explicit=document(dataset("one", ["same"]), dataset("two", ["same"])))


def test_builtin_catalog_resolves_required_systems_without_io():
    catalog = load_catalog(plugins=False, user=False)
    assert catalog.resolve("CMA-MESO").record.dataset_id == "cma_meso_3km"
    assert catalog.resolve("CMA-MESO-1KM").source.args == ("cma_meso_1km/grib2/orig",)
    assert catalog.resolve("CMA-GFS").source.args == ("cma_gfs_gmf/grib2/orig",)
    remote = catalog.resolve("CMA-GFS-CMADaaS")
    assert remote.record.dataset_id == "cma_gfs_gmf_cmadaas"
    assert remote.source.name == "cmadaas"
    assert remote.source.kwargs["kind"] == "model_grid"
    assert remote.source.kwargs["data_code"] == "NAFP_FOR_FTM_GRAPES_GFS_25KM_GLB"
    evidence = remote.record.metadata["data_code_evidence"]
    assert evidence["status"] == "confirmed"
    assert evidence["reviewed_on"] == "2026-08-31"
