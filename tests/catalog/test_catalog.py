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


@pytest.mark.parametrize(("alias", "dataset_id", "data_code", "product_type"), [
    ("CMA-GFS-ANALYSIS-CMADaaS", "cma_gfs_gmf_analysis_cmadaas", "NAFP_ANA_FTM_GRAPES_GFS_25KM_GLB", "deterministic_analysis"),
    ("CMA-GFS-FORECAST-CMADaaS", "cma_gfs_gmf_cmadaas", "NAFP_FOR_FTM_GRAPES_GFS_25KM_GLB", "deterministic_forecast"),
    ("CMA-MESO-3KM-ANALYSIS-CMADaaS", "cma_meso_3km_analysis_cmadaas", "NAFP_GRAPES_MESO_ANA_3KM", "deterministic_analysis"),
    ("CMA-MESO-3KM-FORECAST-CMADaaS", "cma_meso_3km_forecast_cmadaas", "NAFP_GRAPES_MESO_FOR_3KM", "deterministic_forecast"),
    ("CMA-MESO-1KM-ANALYSIS-CMADaaS", "cma_meso_1km_analysis_cmadaas", "NAFP_CEMC_MESO_ANA_1KM", "deterministic_analysis"),
    ("CMA-MESO-1KM-FORECAST-CMADaaS", "cma_meso_1km_forecast_cmadaas", "NAFP_CEMC_MESO_FOR_1KM", "deterministic_forecast"),
    ("CMA-TYM-ANALYSIS-CMADaaS", "cma_tym_analysis_cmadaas", "NAFP_ANA_CMA_TYM_0P09_ASI", "deterministic_analysis"),
    ("CMA-TYM-FORECAST-CMADaaS", "cma_tym_forecast_cmadaas", "NAFP_FOR_CMA_TYM_0P09_ASI", "deterministic_forecast"),
    ("CMA-GEPS-CONTROL-CMADaaS", "cma_geps_control_cmadaas", "NAFP_NWPC_CMAGEPS_GLB_HOR12_D0P5_CONTROL", "ensemble_control_forecast"),
    ("CMA-GEPS-PERTURBATION-CMADaaS", "cma_geps_perturbation_cmadaas", "NAFP_NWPC_CMAGEPS_GLB_HOR12_D0P5_DIS", "ensemble_perturbation_forecast"),
    ("CMA-REPS-CONTROL-CMADaaS", "cma_reps_control_cmadaas", "NAFP_GRAPESREPS_FOR_FTM_CHN", "ensemble_control_forecast"),
    ("CMA-REPS-PERTURBATION-CMADaaS", "cma_reps_perturbation_cmadaas", "NAFP_GRAPESREPS_FOR_FTM_DIS_CHN", "ensemble_perturbation_forecast"),
])
def test_builtin_cmadaas_product_catalog_is_complete(alias, dataset_id, data_code, product_type):
    remote = load_catalog(plugins=False, user=False).resolve(alias)

    assert remote.record.dataset_id == dataset_id
    assert remote.source.name == "cmadaas"
    assert remote.source.kwargs == {"kind": "model_grid", "data_code": data_code}
    assert remote.record.metadata["product_type"] == product_type
    assert remote.record.metadata["data_code_evidence"]["status"] == "confirmed"
