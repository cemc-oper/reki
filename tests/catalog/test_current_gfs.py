"""Current-only product binding and controlled locator/selection regressions."""

import json

import eccodes
import numpy as np
import pytest

from cedarkit_query import QueryError, CompletenessError
from reki import from_source
from reki.catalog import load_catalog, load_resource, plan_source_binding


def encoded(path, *, level=2, hour=6, values=(280, 281, 282, 283), **native):
    path.parent.mkdir(parents=True, exist_ok=True)
    g = eccodes.codes_grib_new_from_samples("regular_ll_sfc_grib2")
    try:
        settings = dict(
            Ni=2,
            Nj=2,
            latitudeOfFirstGridPointInDegrees=50,
            latitudeOfLastGridPointInDegrees=49,
            longitudeOfFirstGridPointInDegrees=100,
            longitudeOfLastGridPointInDegrees=101,
            iDirectionIncrementInDegrees=1,
            jDirectionIncrementInDegrees=1,
            centre=38,
            subCentre=0,
            tablesVersion=4,
            localTablesVersion=0,
            productionStatusOfProcessedData=0,
            productDefinitionTemplateNumber=0,
            discipline=0,
            parameterCategory=0,
            parameterNumber=0,
            typeOfFirstFixedSurface=103,
            scaleFactorOfFirstFixedSurface=0,
            scaledValueOfFirstFixedSurface=level,
            typeOfSecondFixedSurface=255,
            dataDate=20261029,
            dataTime=hour * 100,
            forecastTime=24,
        )
        settings.update(native)
        for key, value in settings.items():
            eccodes.codes_set(g, key, value)
        eccodes.codes_set_values(g, values)
        with path.open("wb") as stream:
            eccodes.codes_write(g, stream)
    finally:
        eccodes.codes_release(g)


def test_binding_and_resource_pins_need_no_business_discovery(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("construction/selection/explain must not discover files")

    monkeypatch.setattr(type(tmp_path), "glob", forbidden)
    source = from_source({"kind": "local", "dataset": "CMA-GFS", "root": str(tmp_path)})
    try:
        selected = source.sel(parameter="t2m", time="2026-10-29T06:00:00Z")
        context = selected.explain().context
        assert context["source"]["dataset"] == "cma_gfs_gmf"
        assert context["source"]["product"] == "orig"
        assert context["source"]["product_version"] == "current"
        assert {r["role"] for r in context["definitions"]} == {
            "catalog",
            "parameter_registry",
            "mappings",
        }
        assert all(len(r["sha256"]) == 64 for r in context["definitions"])
        assert (
            "complete_product_coverage=false" in context["origins"]["provision_scope"]
        )
        assert source.configuration.layout
    finally:
        source.close()


def test_public_local_source_selects_and_reads_registered_layout(tmp_path):
    path = (
        tmp_path
        / "DATA/NAFP/NMC/GRAPES-GFS-GLB/2026/20261029/Z_NAFP_C_BABJ_20261029060000_P_NWPC-GRAPES-GFS-GLB-02400.grib2"
    )
    encoded(path)
    source = from_source(
        {"kind": "local", "dataset": "cma_gfs_gmf", "root": str(tmp_path)}
    )
    try:
        field = source.sel(parameter="t2m", time="2026-10-29T06:00:00+00:00").one()
        ds = field.to_xarray()
        np.testing.assert_array_equal(
            ds.t2m.values.reshape(2, 2), [[280, 281], [282, 283]]
        )
        assert ds.t2m.attrs["units"] == "K"
        assert field.identity.to_dict()["step"] == "PT86400S"
        report = json.loads(ds.attrs["cedarkit_query_report"])
        assert report["context"]["source"]["product_version"] == "current"
        assert report["context"]["source"]["paths"] == [str(path)]
        with pytest.raises(CompletenessError):
            source.sel(parameter="t2m", time="2026-10-29T06:00:00Z").all(
                completeness="required"
            )
    finally:
        source.close()


def test_registered_names_use_supported_domain_and_reject_wrong_pairs(tmp_path):
    path = tmp_path / "field.grib2"
    encoded(path)
    source = from_source({"kind": "file", "dataset": "cma_gfs_gmf", "path": str(path)})
    try:
        assert (
            source.sel(parameter="ps")
            .explain()
            .effective_queries[0]["query"]["parameter"]
            == "cedarkit.ps"
        )
        with pytest.raises(QueryError):
            source.sel(parameter="t2m", step="PT5H")
        with pytest.raises(QueryError):
            source.sel(parameter="t2m", level=10)
        with pytest.raises(QueryError) as error:
            source.sel(
                parameter="cedarkit.t", level_type="pressure", level=600
            ).explain()
        assert error.value.context["reason"] == "mapping_coverage_gap"
        with pytest.raises(QueryError):
            source.sel(parameter="cedarkit.sw").explain()
    finally:
        source.close()


def test_external_catalog_replacement_does_not_inherit_current_binding(tmp_path):
    catalog = load_catalog().to_dict()
    path = tmp_path / "external.json"
    path.write_text(json.dumps(catalog))
    with pytest.raises(QueryError) as error:
        plan_source_binding(
            {"kind": "file", "path": "unopened.grib2", "dataset": "cma_gfs_gmf"},
            context={"catalog": {"path": str(path)}},
        )
    assert error.value.context["reason"] == "missing_context"


def test_historical_or_unknown_product_version_never_falls_back():
    with pytest.raises(QueryError):
        plan_source_binding(
            {"kind": "file", "path": "unopened.grib2", "dataset": "cma_gfs_gmf"},
            product="orig",
            product_version="V6.0",
        )


def test_native_file_keeps_no_default_parameters_or_product(tmp_path):
    config = plan_source_binding(
        {"kind": "file", "path": str(tmp_path / "unopened.grib2")}
    )
    assert config.product is None and config.resources is None
    assert len(config.definitions) == 1


def test_current_resource_pin_rejects_tampering():
    ref = {
        "builtin": "reki.mappings.cma-gfs.current",
        "version": "2",
        "sha256": "0" * 64,
    }
    with pytest.raises(QueryError):
        load_resource(ref, "mappings")


def test_mapping_override_cannot_widen_current_supported_pairs(tmp_path):
    path = tmp_path / "field.grib2"
    encoded(path)
    maps = load_resource(
        {"builtin": "reki.mappings.cma-gfs.current"}, "mappings"
    ).value.to_dict()
    maps["id"] = "controlled.wide-maps"
    for row in maps["mappings"]:
        row["when"] = {}
    replacement = tmp_path / "wide.json"
    replacement.write_text(json.dumps(maps))
    source = from_source(
        {"kind": "file", "dataset": "cma_gfs_gmf", "path": str(path)},
        context={"mappings": {"grib2": {"path": str(replacement)}}},
    )
    try:
        with pytest.raises(QueryError) as error:
            source.sel(parameter="t", level_type="pressure", level=600).explain()
        assert error.value.context["reason"] == "mapping_coverage_gap"
    finally:
        source.close()


def test_mixed_height_and_soil_queries_keep_separate_supported_pairs(tmp_path):
    path = tmp_path / "field.grib2"
    encoded(path)
    source = from_source({"kind": "file", "dataset": "cma_gfs_gmf", "path": str(path)})
    try:
        info = source.sel([{"parameter": "t2m"}, {"parameter": "st(0-10)"}]).explain()
        assert len(info.effective_queries) == 2
        assert {q["query"]["parameter"] for q in info.effective_queries} == {
            "cedarkit.t2m",
            "cedarkit.st-0-10",
        }
    finally:
        source.close()


@pytest.mark.parametrize("dataset", ["CMA-GFS", "CMA-MESO-3KM"])
def test_current_bindings_support_only_reviewed_pressure_pairs(tmp_path, dataset):
    encoded(tmp_path / "unopened.grib2")
    source = from_source(
        {"kind": "file", "dataset": dataset, "path": str(tmp_path / "unopened.grib2")}
    )
    try:
        for name in ["t", "u", "v", "q", "rh"]:
            info = source.sel(
                parameter=name,
                level_type="pressure",
                level=[1000, 925, 850, 700, 500],
                step=["PT0H", "PT12H", "PT24H"],
            ).explain()
            assert info.effective_queries
        for step in (
            ["PT3H", "PT6H", "PT36H"]
            if dataset == "CMA-MESO-3KM"
            else ["PT48H", "PT72H"]
        ):
            assert source.sel(parameter="t2m", step=step).explain().effective_queries
            assert (
                source.sel(parameter="t", level_type="pressure", level=850, step=step)
                .explain()
                .effective_queries
            )
        with pytest.raises(QueryError):
            source.sel(
                parameter="t", level_type="pressure", level=850, step="PT1H"
            ).explain()
        with pytest.raises(QueryError):
            source.sel(parameter="t", level_type="pressure", level=600).explain()
    finally:
        source.close()


def test_meso_local_layout_utc_and_one_terminal(tmp_path):
    path = (
        tmp_path
        / "DATA/NAFP/GRAPES/RAFS/2026/20261029/Z_NAFP_C_BABJ_20261029090000_P_NWPC-GRAPES-3KM-ORIG-00300.grb2"
    )
    encoded(path, hour=9, forecastTime=3)
    encoded(
        path.with_name(path.name.replace("-ORIG-", "-CN-")),
        hour=9,
        forecastTime=3,
        values=(999,) * 4,
    )
    source = from_source(
        {"kind": "local", "dataset": "CMA-MESO-3KM", "root": str(tmp_path)}
    )
    try:
        field = source.sel(
            parameter="t2m", time="2026-10-29T17:00:00+08:00", step="PT3H"
        ).one()
        assert field.identity.to_dict()["time"] == "2026-10-29T09:00:00Z"
        ds = field.to_xarray()
        np.testing.assert_array_equal(
            ds.t2m.values.reshape(2, 2), [[280, 281], [282, 283]]
        )
        assert ds.t2m.attrs["units"] == "K"
        assert json.loads(ds.attrs["cedarkit_query_report"])["context"]["source"][
            "paths"
        ] == [str(path)]
        with pytest.raises(CompletenessError):
            source.sel(parameter="t2m", time="2026-10-29T09:00:00Z", step="PT3H").all(
                completeness="required"
            )
    finally:
        source.close()


def test_meso_soil_uses_actual_layers_and_generic_identity(tmp_path):
    parts = []
    layers = [(0, 0.1), (0.1, 0.3), (0.3, 0.6), (0.6, 1)]
    for i, (top, bottom) in enumerate(layers):
        path = tmp_path / f"soil-{i}.grb2"
        encoded(
            path,
            hour=9,
            forecastTime=12,
            typeOfFirstFixedSurface=106,
            scaleFactorOfFirstFixedSurface=2,
            scaledValueOfFirstFixedSurface=round(top * 100),
            typeOfSecondFixedSurface=106,
            scaleFactorOfSecondFixedSurface=2,
            scaledValueOfSecondFixedSurface=round(bottom * 100),
        )
        parts.append(path.read_bytes())
    path = tmp_path / "all.grb2"
    path.write_bytes(b"".join(parts))
    source = from_source({"kind": "file", "dataset": "cma_meso_3km", "path": str(path)})
    try:
        fields = source.sel(
            [
                {"parameter": "st(0-10)", "step": "PT12H"},
                *[
                    {
                        "parameter": "st",
                        "layer": {"top": top, "bottom": bottom},
                        "step": "PT12H",
                    }
                    for top, bottom in layers[1:]
                ],
            ]
        ).all()
        assert len(fields) == 4
        ds = fields.to_xarray()
        assert len(ds.data_vars) == 4
        assert {v.attrs["cedarkit_parameter_id"] for v in ds.data_vars.values()} == {
            "cedarkit.st",
            "cedarkit.st-0-10",
        }
        assert {
            (v.attrs["layer_top_value"], v.attrs["layer_bottom_value"])
            for v in ds.data_vars.values()
        } == set(layers)
        for var in ds.data_vars.values():
            assert (
                var.attrs["layer_top_type"]
                == var.attrs["layer_bottom_type"]
                == "depth_below_land"
            )
            assert var.attrs["layer_top_unit"] == var.attrs["layer_bottom_unit"] == "m"
            np.testing.assert_array_equal(
                var.values.reshape(2, 2), [[280, 281], [282, 283]]
            )
        with pytest.raises(QueryError):
            source.sel(
                parameter="st", layer={"top": 0.1, "bottom": 0.4}, step="PT12H"
            ).explain()
        with pytest.raises(QueryError):
            source.sel(parameter="st-10-40").explain()
    finally:
        source.close()


def test_gfs_multilevel_multistep_local_assembly(tmp_path):
    for step in [6, 24]:
        blobs = []
        for level in [500, 925]:
            part = tmp_path / f"{step}-{level}.grb2"
            encoded(
                part,
                typeOfFirstFixedSurface=100,
                scaledValueOfFirstFixedSurface=level * 100,
                forecastTime=step,
                values=(step + level,) * 4,
            )
            blobs.append(part.read_bytes())
        path = (
            tmp_path
            / f"DATA/NAFP/NMC/GRAPES-GFS-GLB/2026/20261029/Z_NAFP_C_BABJ_20261029060000_P_NWPC-GRAPES-GFS-GLB-{step:03d}00.grib2"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"".join(blobs))
    source = from_source({"kind": "local", "dataset": "CMA-GFS", "root": str(tmp_path)})
    try:
        fields = source.sel(
            parameter="t",
            time="2026-10-29T06:00:00Z",
            level_type="pressure",
            level=[500, 925],
            step=["PT24H", "PT6H"],
        ).all()
        assert len(fields) == 4
        ds = fields.to_xarray()
        np.testing.assert_array_equal(ds.pressure.values, [925, 500])
        np.testing.assert_array_equal(
            ds.step.values, np.array([6, 24], dtype="timedelta64[h]")
        )
        for step in [6, 24]:
            for level in [925, 500]:
                np.testing.assert_array_equal(
                    ds.t.sel(
                        step=np.timedelta64(step, "h"), pressure=level
                    ).values.reshape(2, 2),
                    np.full((2, 2), step + level),
                )
        np.testing.assert_array_equal(
            ds.valid_time.values.reshape(-1),
            np.array(
                ["2026-10-29T12:00:00", "2026-10-30T06:00:00"], dtype="datetime64[ns]"
            ),
        )
    finally:
        source.close()


@pytest.mark.parametrize("dataset", ["CMA-GFS", "CMA-MESO-3KM"])
def test_current_profiles_reject_historical_resource_versions(dataset):
    name = "cma-gfs" if dataset == "CMA-GFS" else "cma-meso-3km"
    with pytest.raises(QueryError):
        load_resource(
            {"builtin": f"reki.mappings.{name}.current", "version": "0"}, "mappings"
        )


@pytest.mark.parametrize(
    "dataset,subdir,basename",
    [
        ("CMA-MESO-1KM", "CEMC/MESO_1KM/ORI", "CEMC-CMA-MESO-1KM-ORIG"),
        ("CMA-TYM", "NMC/GRAPES-TYM", "NWPC-GRAPES-TYM-ACWP"),
    ],
)
@pytest.mark.parametrize("step", [0, 6, 24])
def test_new_current_analysis_forecast_local_pairs(
    tmp_path, dataset, subdir, basename, step
):
    suffix = "grb2" if dataset == "CMA-MESO-1KM" else "grib2"
    path = (
        tmp_path
        / f"DATA/NAFP/{subdir}/2026/20261029/Z_NAFP_C_BABJ_20261029120000_P_{basename}-{step:03d}00.{suffix}"
    )
    phase = dict(
        typeOfProcessedData=0 if step == 0 else 1,
        typeOfGeneratingProcess=0 if step == 0 else 2,
        significanceOfReferenceTime=0 if step == 0 else 1,
    )
    encoded(path, hour=12, forecastTime=step, **phase)
    source = from_source({"kind": "local", "dataset": dataset, "root": str(tmp_path)})
    try:
        field = source.sel(
            parameter="t2m", time="2026-10-29T20:00:00+08:00", step=f"PT{step}H"
        ).one()
        np.testing.assert_array_equal(
            field.to_xarray().t2m.values.reshape(2, 2), [[280, 281], [282, 283]]
        )
        assert (
            field.metadata["native_fields"]["typeOfProcessedData"]
            == phase["typeOfProcessedData"]
        )
        with pytest.raises(CompletenessError):
            source.sel(
                parameter="t2m", time="2026-10-29T12:00:00Z", step=f"PT{step}H"
            ).all(completeness="required")
        with pytest.raises(QueryError):
            source.sel(parameter="t", level_type="pressure", level=700, step="PT6H")
        with pytest.raises(QueryError):
            source.sel(parameter="t2m", step="PT3H")
    finally:
        source.close()


@pytest.mark.parametrize("dataset", ["CMA-MESO-1KM", "CMA-TYM"])
@pytest.mark.parametrize(
    "step,processed,generating,reference",
    [(0, 1, 2, 1), (6, 0, 0, 0), (6, 1, 0, 1), (0, 0, 2, 0)],
)
def test_new_binding_rejects_incorrect_processing_phase(
    tmp_path, dataset, step, processed, generating, reference
):
    path = tmp_path / "wrong.grb2"
    encoded(
        path,
        forecastTime=step,
        typeOfProcessedData=processed,
        typeOfGeneratingProcess=generating,
        significanceOfReferenceTime=reference,
    )
    source = from_source({"kind": "file", "dataset": dataset, "path": str(path)})
    try:
        with pytest.raises(QueryError):
            source.sel(parameter="t2m", step=f"PT{step}H").one()
    finally:
        source.close()


def test_new_tym_layers_and_meso1_soil_gap(tmp_path):
    path = tmp_path / "unopened.grb2"
    encoded(path)
    tym = from_source({"kind": "file", "dataset": "CMA-TYM", "path": str(path)})
    meso = from_source({"kind": "file", "dataset": "CMA-MESO-1KM", "path": str(path)})
    try:
        assert (
            tym.sel(parameter="st", layer={"top": 0.3, "bottom": 0.6}, step="PT0H")
            .explain()
            .effective_queries
        )
        with pytest.raises(QueryError):
            meso.sel(parameter="st").explain()
    finally:
        tym.close()
        meso.close()
