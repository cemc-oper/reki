"""T13 frozen model_grid execution through the real high-level client path."""

import json
from pathlib import Path

import numpy as np
import pytest

from cedarkit_query import QueryError
from nuwe_cmadaas.music.data import GridArray2D, RequestInfo
from reki.catalog.query_binding import builtin_catalog_snapshot, plan_source_binding
from reki.parameter_adapter import FROZEN_REGISTRY_SHA256
from reki.query_cmadaas import FROZEN_DATA_CODE, plan_frozen_cmadaas, read_frozen_cmadaas


CASES = json.loads((Path(__file__).parent / "core/fixtures/t07_parameter_cases.json").read_text())
RESPONSES = json.loads((Path(__file__).parent / "fixtures/t13/responses.json").read_text())


def _plan(case, **changes):
    query = {"api_version": "cedarkit.query/v1", "domain": "grid", "dataset": CASES["dataset"],
             "parameter": case["parameter_id"], "reference_time": CASES["reference_time"],
             "lead_time": CASES["lead_time"], "vertical": {"type": "surface"},
             "statistic": case["statistic"]}
    query.update(changes)
    return plan_source_binding(query, snapshot=builtin_catalog_snapshot())


def _response(code, *, error_code=0, name=None, shape=None):
    fixture = RESPONSES["responses"][code]
    values = np.asarray(fixture["values"])
    if shape is not None:
        values = values.reshape(shape)
    return GridArray2D(data=values, start_lat=39, end_lat=40, lat_count=2,
                       start_lon=115, end_lon=117, lon_count=3,
                       lats=RESPONSES["grid"]["latitudes"],
                       lons=RESPONSES["grid"]["longitudes"],
                       units=fixture["units"], user_element_name=code if name is None else name,
                       request=RequestInfo(error_code=error_code, error_message="fixture service failure"))


class RecordingClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def callAPI_to_gridArray2D(self, interface_id, params):
        self.calls.append((interface_id, dict(params)))
        return self.responses[params["fcstEle"]]


@pytest.mark.parametrize("case", CASES["cases"], ids=lambda case: case["code"])
def test_offline_high_level_request_and_response_preserve_frozen_case(case, monkeypatch):
    from reki.sources import cmadaas as source_module

    plan = _plan(case)
    with monkeypatch.context() as patch:
        patch.setattr(source_module, "_import_module", lambda name: (_ for _ in ()).throw(
            AssertionError("planning imported the client")))
        execution = plan_frozen_cmadaas(plan, registry_sha256=FROZEN_REGISTRY_SHA256)
    assert execution.request.parameter == case["code"]
    assert execution.request.level_type == 1
    assert execution.request.level == 0
    assert execution.request.start_time.isoformat() == "2026-08-30T00:00:00+00:00"
    assert execution.request.forecast_time.total_seconds() == 86400
    assert execution.request.region["type"] == "rect"
    assert execution.query.statistic["kind"] == case["statistic"]["kind"]
    if case["statistic"]["kind"] == "accum":
        assert execution.query.statistic["window"] == "PT86400S"

    client = RecordingClient({case["code"]: _response(case["code"])})
    result = read_frozen_cmadaas(plan, registry_sha256=FROZEN_REGISTRY_SHA256, client=client)
    assert len(client.calls) == 1
    interface, params = client.calls[0]
    assert interface == "getNafpEleGridInRectByTimeAndLevelAndValidtime"
    assert params == {"dataCode": FROZEN_DATA_CODE, "fcstEle": case["code"],
                      "levelType": "1", "fcstLevel": "0", "time": "20260830000000",
                      "validTime": "24", "minLat": "39.0", "maxLat": "41.0",
                      "minLon": "115.0", "maxLon": "117.0"}
    assert result.execution.query_id == plan.query_id
    assert result.execution.binding_id == plan.binding_id
    assert result.data.name == case["code"]
    assert result.data.attrs["units"] == RESPONSES["responses"][case["code"]]["units"]
    assert result.data.dims == ("latitude", "longitude")
    assert result.data.latitude.values.tolist() == RESPONSES["grid"]["latitudes"]
    assert result.data.longitude.values.tolist() == RESPONSES["grid"]["longitudes"]
    np.testing.assert_array_equal(result.data.values, RESPONSES["responses"][case["code"]]["values"])


@pytest.mark.parametrize("changes,path", [
    ({"member": {"id": "0", "role": "control"}}, "/query/member"),
    ({"vertical": {"type": "isobaric", "unit": "Pa", "values": 50000}}, "/query/vertical"),
    ({"lead_time": ["PT0S", "PT86400S"]}, "/query"),
    ({"statistic": {"kind": "accum", "window": "PT43200S"}}, "/query/statistic"),
    ({"parameter": ["cedarkit.t", "cedarkit.h.any"]}, "/query"),
    ({"coverage": {"crs": "EPSG:4326", "bbox": [115, 39, 117, 41],
                   "relation": "intersects"}}, "/query/coverage"),
])
def test_unsupported_request_fails_before_service(changes, path):
    case = CASES["cases"][0]
    plan = _plan(case, **changes)
    client = RecordingClient({"TEM": _response("TEM")})
    with pytest.raises(QueryError) as caught:
        read_frozen_cmadaas(plan, registry_sha256=FROZEN_REGISTRY_SHA256, client=client)
    assert caught.value.code == "unsupported"
    assert caught.value.path == path
    assert client.calls == []


def test_unfrozen_data_code_and_registry_fail_before_service():
    case = CASES["cases"][0]
    query = _plan(case).query
    from reki.catalog import load_catalog
    from reki.catalog.query_binding import CatalogSnapshot
    catalog = load_catalog(builtin=False, plugins=False, user=False, explicit={
        "api_version": "reki.catalog/v1", "datasets": [{"id": CASES["dataset"], "source": {
            "name": "cmadaas", "kwargs": {"kind": "model_grid", "data_code": "OTHER"}}}]})
    plan = plan_source_binding(query, snapshot=CatalogSnapshot(catalog, "other"))
    with pytest.raises(QueryError) as caught:
        plan_frozen_cmadaas(plan, registry_sha256=FROZEN_REGISTRY_SHA256)
    assert (caught.value.code, caught.value.path) == ("unsupported", "/binding/data_code")
    with pytest.raises(QueryError) as caught:
        plan_frozen_cmadaas(_plan(case), registry_sha256="0" * 64)
    assert caught.value.path == "/vocabulary_version"


def test_service_error_and_mismatched_response_are_reported():
    plan = _plan(CASES["cases"][0])
    client = RecordingClient({"TEM": _response("TEM", error_code=1001)})
    with pytest.raises(QueryError) as caught:
        read_frozen_cmadaas(plan, registry_sha256=FROZEN_REGISTRY_SHA256, client=client)
    assert caught.value.code == "provider_error"
    assert caught.value.context["service_code"] == 1001
    client = RecordingClient({"TEM": _response("TEM", name="WRONG")})
    with pytest.raises(QueryError) as caught:
        read_frozen_cmadaas(plan, registry_sha256=FROZEN_REGISTRY_SHA256, client=client)
    assert caught.value.code == "provider_error"
    assert len(client.calls) == 1
    client = RecordingClient({"TEM": _response("TEM", shape=(3, 2))})
    with pytest.raises(QueryError) as caught:
        read_frozen_cmadaas(plan, registry_sha256=FROZEN_REGISTRY_SHA256, client=client)
    assert caught.value.code == "provider_error"


def test_empty_response_is_reported(monkeypatch):
    import reki.query_cmadaas as module
    import xarray as xr

    class EmptySource:
        def to_xarray(self):
            return xr.DataArray(np.empty((0, 3)), dims=("latitude", "longitude"), name="TEM")

    monkeypatch.setattr(module, "from_source", lambda *args, **kwargs: EmptySource())
    with pytest.raises(QueryError) as caught:
        read_frozen_cmadaas(_plan(CASES["cases"][0]), registry_sha256=FROZEN_REGISTRY_SHA256)
    assert caught.value.code == "provider_error"


def test_unmapped_parameter_never_reaches_service():
    plan = _plan(CASES["cases"][0], parameter="cedarkit.pwat.any")
    client = RecordingClient({"TEM": _response("TEM")})
    with pytest.raises(QueryError) as caught:
        read_frozen_cmadaas(plan, registry_sha256=FROZEN_REGISTRY_SHA256, client=client)
    assert caught.value.code == "unmapped_parameter"
    assert client.calls == []
