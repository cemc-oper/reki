"""The reviewed GFS NSRF surface/top responses keep energy and independent vertical boundaries."""

import json
from importlib.resources import files
from urllib.parse import urlencode

import numpy as np
import pytest
from cedarkit_query import QueryError, SourceError
from nuwe_cmadaas.music import CMADaaSClient, GridArray2D
from reki import from_source
from reki.translation.cmadaas_backend import _unit_response_profile

TIME = "2026-11-02T12:00:00Z"


class Client:
    def __init__(self, unit="W.m-2"):
        self.unit = unit
        self.calls = []

    def callAPI_to_gridArray2D(self, interface, params):
        self.calls.append((interface, dict(params)))
        values = np.array([[0.0, 250.0, -125.0], [1000.0, -500.0, 20.0]])
        if params["validTime"] == "0":
            values[:] = 0
        response = GridArray2D(
            data=values,
            lat_count=2,
            lon_count=3,
            lats=[39.0, 41.0],
            lons=[115.0, 116.0, 117.0],
            units=self.unit,
            user_element_name="NSRF_" + params["levelType"],
        )
        CMADaaSClient._attach_output_metadata(response, interface, params)
        response.request.request_params = urlencode(
            {k.lower(): v for k, v in params.items()}
        )
        return response


@pytest.mark.parametrize(
    "dataset,step,parameter,level_type",
    [
        (dataset, step, parameter, level_type)
        for dataset, step in [
            ("cma_gfs_gmf_analysis_cmadaas", "PT0H"),
            ("cma_gfs_gmf_cmadaas", "PT3H"),
            ("cma_gfs_gmf_cmadaas", "PT6H"),
            ("cma_gfs_gmf_cmadaas", "PT48H"),
        ]
        for parameter, level_type in [
            ("cedarkit.gsw", "surface"),
            ("cedarkit.tsw", "atmosphere_top"),
        ]
    ],
)
def test_reviewed_original_energy_is_not_divided_by_duration(
    dataset, step, parameter, level_type
):
    client = Client()
    with from_source({"kind": "cmadaas", "dataset": dataset}, client=client) as source:
        field = source.sel(
            parameter=parameter, level_type=level_type, time=TIME, step=step
        ).one(completeness="required")
        data = field.to_xarray()[parameter.rsplit(".", 1)[-1]].squeeze(drop=True)
        np.testing.assert_array_equal(
            data.values,
            np.zeros((2, 3))
            if step == "PT0H"
            else [[0.0, 250.0, -125.0], [1000.0, -500.0, 20.0]],
        )
        assert data.attrs["units"] == field.metadata["source_unit"] == "J/m2"
        assert field.metadata["response_unit"] == "W.m-2"
        assert field.metadata["source_unit_basis"] == "product_contract"
        assert field.metadata["response_unit_profile"] == "gfs_nsrf_accumulated_energy"
        assert field.report.overall["status"] == "complete"
        assert field.metadata["statistical_interval"]["start"] == TIME
    assert len(client.calls) == 1
    assert client.calls[0][1]["levelType"] == (
        "8" if level_type == "atmosphere_top" else "1"
    )
    assert client.calls[0][1]["fcstLevel"] == "0"


@pytest.mark.parametrize("unit", ["K", "W/m2", "", None])
def test_unreviewed_or_missing_response_units_remain_errors(unit):
    client = Client(unit)
    with from_source(
        {"kind": "cmadaas", "dataset": "cma_gfs_gmf_cmadaas"}, client=client
    ) as source:
        with pytest.raises(SourceError) as caught:
            source.sel(
                parameter="cedarkit.gsw", level_type="surface", time=TIME, step="PT6H"
            ).one()
        assert caught.value.code == "metadata_interpretation_failed"


@pytest.mark.parametrize(
    "change",
    [
        {"step": "PT0H"},
        {"step": "PT9H"},
        {"time": "2026-11-03T12:00:00Z"},
        {
            "statistics": {
                "operation": "accumulation",
                "over": "time",
                "interval": {
                    "start": "2026-11-02T15:00:00Z",
                    "end": "2026-11-02T18:00:00Z",
                },
            }
        },
    ],
)
def test_unverified_cells_and_nonzero_start_are_rejected_before_io(change):
    client = Client()
    with from_source(
        {"kind": "cmadaas", "dataset": "cma_gfs_gmf_cmadaas"}, client=client
    ) as source:
        with pytest.raises(QueryError):
            source.sel(
                {
                    "parameter": "cedarkit.gsw",
                    "level_type": "surface",
                    "time": TIME,
                    "step": "PT6H",
                    **change,
                }
            ).one()
    assert not client.calls


def test_unit_interpretation_is_specific_to_product_element_parameter_and_statistic():
    base = files("reki.catalog").joinpath("builtin")
    mappings = json.loads((base / "current-cmadaas-mappings.json").read_text())
    mapping = next(
        m for m in mappings["mappings"] if m["parameter_id"] == "cedarkit.gsw"
    )
    definition = next(
        p
        for p in json.loads((base / "current-cmadaas-parameters.json").read_text())[
            "parameters"
        ]
        if p["parameter_id"] == "cedarkit.gsw"
    )
    service = {
        "data_code": "NAFP_ANA_FTM_GRAPES_GFS_25KM_GLB",
        "interface_contract": {"id": "cmadaas.grid-array2d.forecast", "version": 2},
    }
    assert (
        _unit_response_profile(mapping, service, definition)
        == "gfs_nsrf_accumulated_energy"
    )
    for value in [
        {**service, "data_code": "OTHER"},
        {
            **service,
            "interface_contract": {"id": "cmadaas.grid-array2d.forecast", "version": 1},
        },
    ]:
        assert _unit_response_profile(mapping, value, definition) is None
    for parameter, element in [("cedarkit.other", "NSRF"), ("cedarkit.gsw", "HEFU")]:
        changed = json.loads(json.dumps(mapping))
        changed["parameter_id"] = parameter
        changed["native"]["match"]["fcstEle"] = element
        assert _unit_response_profile(changed, service, definition) is None
    changed = json.loads(json.dumps(definition))
    changed["fixed_conditions"]["statistics"]["operation"] = "average"
    assert _unit_response_profile(mapping, service, changed) is None
