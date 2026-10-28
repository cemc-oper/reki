"""Actual coordinate domains, units, conflicts and metadata, all SYNTHETIC."""

from dataclasses import replace
import numpy as np
import pytest
import xarray as xr

from cedarkit_query import Query, QueryError

TIME = "2026-01-01T00:00:00Z"


def field(q, **changes):
    data = q.to_dict()
    data.pop("valid_time", None)
    return Query({**data, **changes})


def layer(bottom, top, **extra):
    return Query(
        parameter="synthetic.st",
        time=TIME,
        step="PT0H",
        level_type="depth_below_land",
        layer=dict(bottom=bottom, top=top),
        **extra,
    )


def test_internal_holes_and_absent_coordinate_not_fabricated(factory, q):
    q500_6 = field(q, level=500)
    q850_12 = field(q, step="PT12H")
    absent = field(q, level=500, step="PT12H")
    source, _, _ = factory([q, q500_6, q850_12], [q, q500_6, q850_12, absent])
    ds = source.sel(field(q, level=[850, 500], step=["PT6H", "PT12H"])).to_xarray()
    assert ds.t.dims == ("time", "step", "pressure", "latitude", "longitude")
    np.testing.assert_array_equal(ds.pressure, [850, 500])
    assert ds.pressure.attrs["units"] == "hPa"
    assert np.isnan(ds.t.isel(step=1, pressure=1)).all()
    assert ds.t.attrs["cedarkit_parameter_id"] == "synthetic.t"
    assert ds.time.attrs["timezone"] == ds.valid_time.attrs["timezone"] == "UTC"
    assert ds.valid_time.dims == ("time", "step")
    assert ds.step.dtype.kind == "m"
    np.testing.assert_array_equal(ds.latitude, [45.0, 40.0])
    source, _, _ = factory([q, q850_12], [q, q500_6, q850_12, absent])
    ds = source.sel(field(q, level=[850, 500], step=["PT6H", "PT12H"])).to_xarray()
    assert ds.sizes["pressure"] == 1


def test_paired_requests_do_not_create_expected_cross_combinations(factory, q):
    other = field(q, level=500, step="PT12H")
    source, _, _ = factory([q, other], [q, other])
    result = source.sel([q, other]).all(completeness="required")
    assert result.report.overall["expected_count"] == 2
    assert result.report.overall["status"] == "complete"
    assert result.to_xarray().t.isnull().sum() == 8


def test_zero_match_empty_dataset_and_all_nan_field_exists(factory, q):
    source, _, _ = factory([], [q])
    ds = source.sel(q).to_xarray()
    assert not ds.dims and not ds.data_vars
    source, backend, refs = factory([q], [q])

    def load():
        return xr.DataArray(
            np.full((2, 2), np.nan),
            dims=("latitude", "longitude"),
            coords={"latitude": [45.0, 40.0], "longitude": [100.0, 105.0]},
        )

    backend.records = [replace(refs[0], load=load)]
    fields = source.sel(q).all(completeness="required")
    assert fields.report.overall["satisfied_count"] == 1
    assert fields.to_xarray().t.isnull().all()


def test_time_step_remain_independent_and_fine_precision(factory, q):
    a = field(q, time="2026-01-01T00:00:00.000000001Z", step="PT1.000000002S")
    b = field(q, time="2026-01-01T00:00:01.000000001Z", step="PT0.000000002S")
    source, _, _ = factory([a, b], [a, b])
    ds = source.sel([a, b]).to_xarray(completeness="required")
    assert ds.sizes["time"] == ds.sizes["step"] == 2
    assert ds.valid_time.values[0, 1] == ds.valid_time.values[1, 0]
    assert ds.time.values[0] == np.datetime64("2026-01-01T00:00:00.000000001")


def test_pressure_unit_conversion_and_height_sort(factory, q):
    query = field(q, level=85000, level_unit="Pa")
    source, _, _ = factory([query], [query])
    assert source.sel(query).to_xarray().pressure.values[0] == 850
    low = field(q, level_type="height_above_ground", level=2, level_unit="m")
    high = field(q, level_type="height_above_ground", level=10, level_unit="m")
    source, _, _ = factory([high, low], [high, low])
    ds = source.sel([high, low]).to_xarray()
    np.testing.assert_array_equal(ds.height_above_ground, [2, 10])


def test_member_axis_roles_sorted_and_no_implicit_control(factory, q):
    a, b = (
        field(q, member=2, member_role="perturbation"),
        field(q, member=0, member_role="control"),
    )
    source, _, _ = factory(
        [a, b], [a, b], context={"member_roles": {"0": "control", "2": "perturbation"}}
    )
    ds = source.sel([a, b]).to_xarray()
    assert ds.t.dims == ("time", "step", "member", "pressure", "latitude", "longitude")
    np.testing.assert_array_equal(ds.member, [0, 2])
    np.testing.assert_array_equal(ds.member_role, ["control", "perturbation"])
    source, _, _ = factory([q], [q])
    assert "member" not in source.sel(q).to_xarray().dims


def test_layers_are_variables_with_canonical_names_and_six_attrs(factory):
    a, b = layer(0.3, 0.1), layer(0.5, 0.3)
    source, _, _ = factory([a, b], [a, b])
    ds = source.sel([a, b]).to_xarray()
    name = "st__layer__depth_below_land__bottom_0.3m__top_0.1m"
    assert set(ds.data_vars) == {
        name,
        "st__layer__depth_below_land__bottom_0.5m__top_0.3m",
    }
    assert "layer" not in ds.dims and "depth_below_land" not in ds.dims
    assert {k: v for k, v in ds[name].attrs.items() if k.startswith("layer_")} == dict(
        layer_bottom_type="depth_below_land",
        layer_bottom_value=0.3,
        layer_bottom_unit="m",
        layer_top_type="depth_below_land",
        layer_top_value=0.1,
        layer_top_unit="m",
    )
    with pytest.raises(QueryError) as exc:
        source.sel([a, b]).to_xarray(rename="soil")
    assert exc.value.code == "multiple_variables"
    renamed = source.sel(a).to_xarray(rename="soil")
    assert renamed.soil.attrs["cedarkit_parameter_name"] == "st"
    assert renamed.soil.attrs["layer_bottom_value"] == 0.3


def test_named_boundaries_and_surface_no_fictitious_values(factory):
    query = Query(
        parameter="synthetic.st",
        layer={"bottom": {"type": "surface"}, "top": {"type": "atmosphere_top"}},
    )
    source, _, _ = factory([query], [query])
    ds = source.sel(query).to_xarray()
    attrs = next(iter(ds.data_vars.values())).attrs
    assert attrs["layer_bottom_type"] == "surface" and "layer_bottom_value" not in attrs
    assert "layer_bottom_unit" not in attrs
    query = Query(parameter="synthetic.t", level_type="surface")
    source, _, _ = factory([query], [query])
    ds = source.sel(query).to_xarray()
    assert (
        ds.t.dims == ("latitude", "longitude") and ds.t.attrs["level_type"] == "surface"
    )


def test_rename_validation_and_missing_variable_no_fabrication(factory, q):
    u = field(q, parameter="synthetic.u")
    source, _, _ = factory([q], [q, u])
    ds = source.sel([q, u]).to_xarray(rename={"u": "wind", "t": "temperature"})
    assert set(ds.data_vars) == {"temperature"}
    with pytest.raises(QueryError):
        source.sel(q).to_xarray(rename={"unknown": "x"})
    for name in ("pressure", "latitude", "valid_time", ""):
        with pytest.raises(QueryError):
            source.sel(q).to_xarray(rename=name)


def test_duplicate_positions_cannot_be_renamed_and_first_can_convert(factory, q):
    source, backend, refs = factory([q, q], [q])
    assert source.sel(q).first().to_xarray().t.size == 4
    with pytest.raises(QueryError) as exc:
        source.sel(q).all().to_xarray(rename="other")
    assert exc.value.code == "duplicate_field"


def test_grid_definitions_and_coordinates_and_vertical_conflicts(factory, q):
    q500 = field(q, level=500)
    source, backend, refs = factory([q, q500], [q, q500])
    backend.records = [
        refs[0],
        replace(refs[1], grid={"projection": "SYNTHETIC-different"}),
    ]
    assert len(source.sel([q, q500]).all()) == 2
    with pytest.raises(QueryError) as exc:
        source.sel([q, q500]).to_xarray()
    assert exc.value.code == "incompatible_grid" and backend.loads == 0

    def shifted():
        return xr.DataArray(
            np.ones((2, 2)),
            dims=("latitude", "longitude"),
            coords={"latitude": [44.0, 40.0], "longitude": [100.0, 105.0]},
        )

    backend.records = [refs[0], replace(refs[1], load=shifted)]
    with pytest.raises(QueryError) as exc:
        source.sel([q, q500]).to_xarray()
    assert exc.value.code == "incompatible_grid"
    backend.records = [
        refs[0],
        replace(
            refs[1],
            metadata={
                **dict(refs[1].metadata),
                "vertical_definition": {"id": "DIFFERENT"},
            },
        ),
    ]
    with pytest.raises(QueryError) as exc:
        source.sel([q, q500]).to_xarray()
    assert exc.value.code == "incompatible_grid"


def test_source_units_convert_only_after_loading_and_report_not_value_quality(
    factory, q
):
    source, backend, _ = factory(
        [q],
        [q],
        metadata={"source_unit": "degC", "quantity_kind": "absolute_temperature"},
    )
    result = source.sel(q).all()
    assert backend.loads == 0
    ds = result.to_xarray()
    np.testing.assert_allclose(ds.t, 274.15)
    assert ds.t.attrs["units"] == "K" and backend.loads == 1


@pytest.mark.parametrize(
    "meta", [{"source_unit": None}, {"source_unit": "m"}, {"source_unit": "degC"}]
)
def test_unknown_incompatible_or_unproven_affine_units_fail(factory, q, meta):
    source, backend, _ = factory([q], [q], metadata=meta)
    with pytest.raises(QueryError) as exc:
        source.sel(q).to_xarray()
    assert exc.value.code == "unsupported" and backend.loads == 0


def test_native_single_field_rename_does_not_fabricate_parameter_id(factory):
    query = Query(native={"grib": {"discipline": 0, "parameterNumber": 0}})
    source, _, _ = factory([query], None, no_resources=True)
    ds = source.sel(query).to_xarray(rename="native_field")
    assert "cedarkit_parameter_id" not in ds.native_field.attrs
    assert ds.native_field.attrs["units"] == "K"


def test_exact_registered_layer_variant_uses_business_name(factory):
    from cedarkit_query import normalize_query

    base = normalize_query(layer(0.3, 0.1))
    exact = Query({**base.to_dict(), "parameter": "synthetic.st.variant"})
    definition = dict(
        parameter_id="synthetic.st.variant",
        name="st(SYNTHETIC-layer)",
        parent="synthetic.st",
        fixed_conditions={"layer": base.to_dict()["layer"]},
    )
    source, _, _ = factory([exact], [exact], extra_parameters=[definition])
    ds = source.sel(base).to_xarray(completeness="required")
    assert set(ds.data_vars) == {"st(SYNTHETIC-layer)"}
    assert (
        ds["st(SYNTHETIC-layer)"].attrs["cedarkit_parameter_id"]
        == "synthetic.st.variant"
    )


def test_model_level_vertical_definition_and_depth_ascending(factory, q):
    a = q.to_dict()
    a.pop("level_unit")
    a.update(level_type="model_level", level=2)
    b = {**a, "level": 1}
    source, _, _ = factory([a, b], [Query(a), Query(b)])
    ds = source.sel([a, b]).to_xarray()
    np.testing.assert_array_equal(ds.model_level, [1, 2])
    assert "units" not in ds.model_level.attrs


def test_projected_grid_keeps_definition_and_auxiliary_latlon(factory, q):
    source, backend, refs = factory([q], [q])

    def load():
        data = xr.DataArray(
            np.ones((2, 2)),
            dims=("y", "x"),
            coords={
                "y": ("y", [2000.0, 1000.0], {"units": "m"}),
                "x": ("x", [1000.0, 2000.0], {"units": "m"}),
                "latitude": (("y", "x"), [[40.0, 40.0], [39.0, 39.0]]),
                "longitude": (("y", "x"), [[100.0, 101.0], [100.0, 101.0]]),
                "crs": 0,
            },
            attrs={"grid_mapping": "crs"},
        )
        data.crs.attrs["grid_mapping_name"] = "SYNTHETIC_projection"
        return data

    backend.records = [replace(refs[0], load=load)]
    ds = source.sel(q).to_xarray()
    assert ds.t.dims == ("time", "step", "pressure", "y", "x")
    assert ds.t.attrs["grid_mapping"] == "crs"
    assert ds.crs.attrs["grid_mapping_name"] == "SYNTHETIC_projection"
    assert (
        ds.latitude.dims == ("y", "x") and ds.latitude.attrs["units"] == "degrees_north"
    )


def test_default_name_ambiguity_cannot_be_resolved_by_rename(factory, q):
    height = field(q, level_type="height_above_ground", level=2, level_unit="m")
    source, _, _ = factory([q, height], [q, height])
    with pytest.raises(QueryError) as exc:
        source.sel([q, height]).to_xarray(rename={"t": "temperature"})
    assert exc.value.code == "multiple_variables"


def test_unregistered_native_quantities_cannot_silently_share_a_variable(factory):
    a = Query(time=TIME, native={"grib": {"parameterNumber": 0}})
    b = Query(time="2026-01-01T06:00:00Z", native={"grib": {"parameterNumber": 1}})
    source, _, _ = factory([a, b], None, no_resources=True)
    with pytest.raises(QueryError) as exc:
        source.sel([a, b]).to_xarray(rename="invented_shared_quantity")
    assert exc.value.code == "multiple_variables"
