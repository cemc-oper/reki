"""SYNTHETIC single-grid transport only; no actual MUSIC request or credential use."""

import json
import numpy as np
import pytest
import xarray as xr

from cedarkit_query import QueryError, SourceError
from reki.catalog import plan_source_binding
from reki.selection.core import construct_source
from reki.translation.cmadaas import InterfaceContract
from reki.translation.cmadaas_backend import CmadaasBackend


class Transport:
    def __init__(self):
        self.requests = []
        self.closes = 0
        self.truncated = False
        self.conflict = False

    def request(self, interface, method, parameters):
        self.requests.append(dict(parameters))
        value = float(parameters["fcstLevel"])
        data = xr.DataArray(
            np.full((2, 2), value),
            dims=("latitude", "longitude"),
            coords={"latitude": [50.0, 49.0], "longitude": [100.0, 101.0]},
        )
        return dict(
            response_kind="RetGridArray2D",
            record_count=1,
            request_parameters=dict(parameters),
            metadata={"fcstLevel": "OTHER"} if self.conflict else {},
            unit="K",
            data=data,
            truncated=self.truncated,
        )

    def close(self):
        self.closes += 1


@pytest.fixture
def source_factory(tmp_path):
    def make(*, owns=False, method="SYNTHETIC.method", transport_factory=None):
        ref = {"id": "SYNTHETIC.single-grid", "version": 1}
        contract = InterfaceContract(
            ref["id"],
            ref["version"],
            "SYNTHETIC.interface",
            method,
            {
                "time": "time",
                "step": "validTime",
                "level_type": "levelType",
                "level": "fcstLevel",
            },
            {
                "time": "time",
                "step": "validTime",
                "level_type": "levelType",
                "level": "fcstLevel",
            },
            "level_type_and_level",
        )
        parameters = dict(
            api_version="cedarkit.parameters/v1",
            id="SYNTHETIC.parameters",
            version="1",
            parameters=[
                dict(
                    parameter_id="synthetic.t",
                    name="t",
                    unit="K",
                    fixed_conditions={
                        "statistics": {"over": "time", "operation": "instantaneous"}
                    },
                )
            ],
        )
        mappings = dict(
            api_version="cedarkit.mappings/v1",
            id="SYNTHETIC.cmadaas",
            version="1",
            backend="cmadaas",
            tables=[
                dict(
                    id="SYNTHETIC.pressure",
                    key_kind="level_type_and_level",
                    applies_to={},
                    evidence=["SYNTHETIC joint key definition"],
                    rows=[
                        dict(
                            id="p1000",
                            native={"level_type": "P", "level": "1000"},
                            canonical={"level_type": "pressure", "level": 1000},
                        ),
                        dict(
                            id="p850",
                            native={"level_type": "P", "level": "850"},
                            canonical={"level_type": "pressure", "level": 850},
                        ),
                    ],
                )
            ],
            mappings=[
                dict(
                    id="SYNTHETIC.t",
                    parameter_id="synthetic.t",
                    backend="cmadaas",
                    applies_to=dict(
                        dataset="SYNTHETIC",
                        product="SYNTHETIC.p",
                        product_version="SYNTHETIC-v1",
                    ),
                    when={},
                    native=dict(
                        match=dict(dataCode="SYNTHETIC_DATA", fcstEle="SYNTHETIC_T"),
                        translate={
                            "vertical": {
                                "rule": "cmadaas.vertical_table",
                                "config": {"table": "SYNTHETIC.pressure"},
                            },
                            "time": {"rule": "cmadaas.time_fields"},
                            "statistics": {"rule": "cmadaas.statistics_fields"},
                            "unit": {"rule": "common.value_unit"},
                        },
                    ),
                    evidence=["SYNTHETIC controlled single-grid contract only"],
                )
            ],
        )
        catalog = dict(
            api_version="cedarkit.catalog/v1",
            id="SYNTHETIC.catalog",
            version="1",
            datasets=[
                dict(
                    id="SYNTHETIC",
                    mappings={"cmadaas": {"path": "maps.json"}},
                    products=[
                        dict(
                            id="SYNTHETIC.p",
                            version="SYNTHETIC-v1",
                            scope={},
                            provides=[
                                {
                                    "parameter": "synthetic.t",
                                    "level_type": "pressure",
                                    "level": [1000, 850],
                                }
                            ],
                            populations=[],
                            methods=[],
                            sources=[
                                dict(
                                    id="SYNTHETIC.service",
                                    kind="cmadaas",
                                    data_code="SYNTHETIC_DATA",
                                    interface_contract=ref,
                                    time_zone="Asia/Shanghai",
                                )
                            ],
                            evidence=["SYNTHETIC"],
                        )
                    ],
                )
            ],
        )
        for name, data in (
            ("params", parameters),
            ("maps", mappings),
            ("catalog", catalog),
        ):
            (tmp_path / (name + ".json")).write_text(json.dumps(data))
        client = (
            Transport() if transport_factory is None else transport_factory(contract)
        )
        config = plan_source_binding(
            dict(kind="cmadaas", dataset="SYNTHETIC"),
            context=dict(
                catalog={"path": str(tmp_path / "catalog.json")},
                parameter_registry={"path": str(tmp_path / "params.json")},
            ),
            product="SYNTHETIC.p",
            product_version="SYNTHETIC-v1",
            client=client,
            interface_contracts={(ref["id"], ref["version"])},
        )
        return construct_source(
            config, CmadaasBackend(config, contract, client, owns_transport=owns)
        ), client

    return make


def selected(source, levels=(1000, 850)):
    return source.sel(
        parameter="t",
        time="2026-01-01T00:00:00Z",
        step="PT6H",
        level_type="pressure",
        level=list(levels),
    )


def test_service_plan_no_calls_and_exact_association_after_acquisition(source_factory):
    source, client = source_factory()
    selection = selected(source)
    info = selection.explain()
    assert not client.requests
    assert info.analysis["translations"][0]["checks"][0]["status"] == "pending"
    fields = selection.all()
    assert len(fields) == 2 and len(client.requests) == 2
    assert all(
        p["time"] == "20260101080000" and p["validTime"] == "6" for p in client.requests
    )
    report = fields.report
    assert report.translations[0]["checks"][0]["status"] == "passed"
    ds = fields.to_xarray()
    np.testing.assert_array_equal(ds.pressure, [1000, 850])
    assert ds.t.values.flat[0] == 1000
    assert len(client.requests) == 2  # Already acquired response values are reused.
    assert fields[0].metadata["fact_origins"]["time"]["step"] == "request_association"
    assert "request_parameters" not in report.to_json()
    source.close()
    assert client.closes == 0 and ds.t.values.flat[0] == 1000


def test_first_stops_other_calls_and_retains_branch_state(source_factory):
    source, client = source_factory()
    field = selected(source).first()
    assert len(client.requests) == 1
    states = [
        b["execution"]["status"] for b in field.report.translations[0]["branches"]
    ]
    assert sorted(states) == ["not_started", "stopped_early"]
    assert field.report.translations[0]["checks"][0]["status"] == "passed"
    assert field.report.overall["status"] == "unchecked"


@pytest.mark.parametrize("problem", ["truncated", "conflict"])
def test_service_failure_never_becomes_missing_or_partial_success(
    source_factory, problem
):
    source, client = source_factory()
    setattr(client, problem, True)
    with pytest.raises(SourceError) as exc:
        selected(source).all()
    assert exc.value.code == (
        "incomplete_response"
        if problem == "truncated"
        else "metadata_interpretation_failed"
    )
    assert "report" not in exc.value.to_dict()


def test_owned_transport_closed_once_and_unbounded_layer_not_enumerated_from_table(
    source_factory,
):
    source, client = source_factory(owns=True)
    with pytest.raises(QueryError) as exc:
        source.sel(
            parameter="t",
            time="2026-01-01T00:00:00Z",
            step="PT6H",
            level_type="pressure",
        )
    assert exc.value.context["reason"] == "unsafe_candidate_expansion"
    assert not client.requests
    selected(source, (850,)).one()
    source.close()
    source.close()
    assert client.closes == 1


@pytest.mark.parametrize(
    "error,code",
    [
        (TimeoutError, "timeout"),
        (PermissionError, "permission_denied"),
        (ConnectionError, "io_error"),
    ],
)
def test_transport_errors_keep_structured_safe_location(source_factory, error, code):
    source, client = source_factory()

    def fail(*args):
        raise error("SYNTHETIC private transport detail")

    client.request = fail
    with pytest.raises(SourceError) as exc:
        selected(source).all()
    assert exc.value.code == code
    assert exc.value.context["request_index"] == 0
    assert "private transport detail" not in json.dumps(exc.value.to_dict())
    assert "report" not in exc.value.to_dict()


def test_absent_response_wrapper_is_metadata_failure(source_factory):
    source, client = source_factory()
    client.request = lambda *args: None
    with pytest.raises(SourceError) as exc:
        selected(source).all()
    assert exc.value.code == "metadata_interpretation_failed"
    assert exc.value.context["reason"] == "missing_native_metadata"
    assert exc.value.context["request_index"] == 0


class OfflineHTTP:
    """Exercise the real client/connection/protobuf path with no sockets."""

    def __init__(self):
        self.calls = []
        self.content = None
        self.failure = None
        self.closes = 0

    def get(self, url, **kwargs):
        from types import SimpleNamespace
        from urllib.parse import parse_qs, urlsplit
        from nuwe_cmadaas.music import apiinterface_pb2 as pb

        values = parse_qs(urlsplit(url).query)
        # Store only explicitly selected business arguments, never signed URLs.
        self.calls.append(
            {
                k: values[k][0]
                for k in (
                    "interfaceId",
                    "method",
                    "dataCode",
                    "fcstEle",
                    "time",
                    "validTime",
                    "levelType",
                    "fcstLevel",
                )
            }
        )
        if self.failure:
            raise self.failure("SYNTHETIC private transport detail")
        if self.content is not None:
            return SimpleNamespace(content=self.content, status_code=200)
        msg = pb.RetGridArray2D()
        msg.request.errorCode = 0
        msg.request.rowCount = 2  # A grid dimension counter, not field count.
        msg.request.colCount = 2
        msg.latCount, msg.lonCount = 2, 2
        msg.startLat, msg.endLat, msg.latStep = 50.0, 49.0, -1.0
        msg.startLon, msg.endLon, msg.lonStep = 100.0, 101.0, 1.0
        msg.lats.extend([50.0, 49.0])
        msg.lons.extend([100.0, 101.0])
        msg.units, msg.userEleName = "K", "SYNTHETIC_RETURN_NAME"
        value = float(values["fcstLevel"][0])
        msg.data.extend([value, value + 1, value + 2, value + 3])
        return SimpleNamespace(content=msg.SerializeToString(), status_code=200)

    def close(self):
        self.closes += 1


@pytest.fixture
def nuwe_source(source_factory, monkeypatch):
    import socket
    from nuwe_cmadaas.music.client import CMADaaSClient
    from reki.translation.nuwe_transport import NuweGridTransport

    def no_socket(*args, **kwargs):
        raise AssertionError("offline fixture attempted socket I/O")

    monkeypatch.setattr(socket.socket, "connect", no_socket)
    http = OfflineHTTP()
    client = CMADaaSClient(
        server_ip="synthetic.invalid",
        server_port=8080,
        server_id="SYNTHETIC",
        user="SYNTHETIC_USER",
        password="SYNTHETIC_PASSWORD",
        connection_timeout=1,
        read_timeout=2,
        transport=http,
        log_policy="summary",
        max_retries=0,
    )
    source, transport = source_factory(
        owns=True,
        method="callAPI_to_gridArray2D",
        transport_factory=lambda contract: NuweGridTransport(client, contract),
    )
    return source, transport, client, http


def test_real_nuwe_client_offline_pipeline_keeps_raw_invocation_and_provenance(
    nuwe_source,
):
    from nuwe_cmadaas.music.data import GridArray2D

    source, transport, client, http = nuwe_source
    selection = selected(source)
    selection.explain()
    assert not http.calls
    fields = selection.all()
    assert len(fields) == len(http.calls) == 2
    record = fields[0].metadata["call_record"]
    assert record.response["invocation"].response is record.response["raw_response"]
    raw = record.response["raw_response"]
    assert isinstance(raw, GridArray2D) and raw.request.row_count == 2
    # The client copies these attrs from the request. They are not native facts.
    assert raw.metadata["level"] == record.parameters["fcstLevel"]
    assert record.response["metadata"] == {}
    assert fields[0].metadata["fact_origins"]["time"]["step"] == "request_association"
    ds = fields.to_xarray()
    np.testing.assert_array_equal(ds.pressure, [1000, 850])
    np.testing.assert_array_equal(
        ds.t.values.reshape(2, 2, 2),
        [[[1000, 1001], [1002, 1003]], [[850, 851], [852, 853]]],
    )
    assert all(
        c["method"] == "callAPI_to_gridArray2D" and c["time"] == "20260101080000"
        for c in http.calls
    )
    report = fields.report.to_json()
    assert fields.report.context["origins"]["native_library"].startswith(
        "nuwe-cmadaas@"
    )
    assert all(
        s not in report
        for s in (
            "SYNTHETIC_PASSWORD",
            "SYNTHETIC_USER",
            "request_parameters",
            "raw_response",
        )
    )
    assert len(http.calls) == 2
    source.close()
    source.close()
    assert transport._closed and http.closes == 0
    assert client.transport is http
    assert ds.t.values.flat[0] == 1000


@pytest.mark.parametrize(
    "content,code",
    [
        (
            b'{"returnCode":-1004,"flag":"slb","returnMessage":"SYNTHETIC secret response"}',
            "authentication_failed",
        ),
        (
            b'{"returnCode":-42,"flag":"slb","returnMessage":"SYNTHETIC secret response"}',
            "service_error",
        ),
        (b"not protobuf", "decode_failed"),
        (b"", "metadata_interpretation_failed"),
    ],
)
def test_real_nuwe_client_response_failures_never_become_absence(
    nuwe_source, content, code
):
    source, transport, client, http = nuwe_source
    http.content = content
    with pytest.raises(SourceError) as exc:
        selected(source).all()
    assert exc.value.code == code
    assert exc.value.context["request_index"] == 0
    assert "SYNTHETIC secret response" not in json.dumps(exc.value.to_dict())
    assert "report" not in exc.value.to_dict()
    source.close()
    assert http.closes == 0


@pytest.mark.parametrize(
    "failure,code", [("Timeout", "timeout"), ("ConnectionError", "io_error")]
)
def test_real_nuwe_client_transport_status_is_translated(nuwe_source, failure, code):
    import requests

    source, transport, client, http = nuwe_source
    http.failure = getattr(requests, failure)
    with pytest.raises(SourceError) as exc:
        selected(source).all()
    assert exc.value.code == code
    assert exc.value.context["request_index"] == 0
    assert "private transport detail" not in json.dumps(exc.value.to_dict())
    source.close()


def test_raw_invocation_cannot_be_replaced_by_another_response(nuwe_source):
    from reki.translation import cmadaas
    from nuwe_cmadaas.music.data import GridArray2D

    source, transport, client, http = nuwe_source
    fields = selected(source, levels=(850,)).all()
    record = fields[0].metadata["call_record"]
    changed = {**record.response, "raw_response": GridArray2D()}
    with pytest.raises(SourceError) as exc:
        cmadaas.associate(record.contract, record.parameters, changed, request_index=4)
    assert exc.value.context["reason"] == "inconsistent_native_metadata"
    assert exc.value.context["request_index"] == 4
    source.close()
