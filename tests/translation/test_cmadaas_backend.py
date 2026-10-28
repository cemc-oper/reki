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
    def make(
        *,
        owns=False,
        method="SYNTHETIC.method",
        transport_factory=None,
        interface_id="SYNTHETIC.interface",
        raw_contract=False,
    ):
        ref = {"id": "SYNTHETIC.single-grid", "version": 1}
        contract = InterfaceContract(
            ref["id"],
            ref["version"],
            interface_id,
            method,
            {
                "time": "time",
                "step": "validTime",
                "level_type": "levelType",
                "level": "fcstLevel",
            },
            {}
            if raw_contract
            else {
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
                    "fcstMember",
                    "minLat",
                    "maxLat",
                    "minLon",
                    "maxLon",
                )
                if k in values
            }
        )
        if self.failure:
            raise self.failure("SYNTHETIC private transport detail")
        if self.content is not None:
            return SimpleNamespace(content=self.content, status_code=200)
        msg = pb.RetGridArray2D()
        msg.request.errorCode = 0
        msg.request.rowCount = 2  # Synthetic counter; never treated as field count.
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
        interface_id="getNafpEleGridByTimeAndLevelAndValidtime",
        raw_contract=True,
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


@pytest.mark.parametrize(
    "interface,analysis,member,rectangle",
    [
        ("getNafpAnaEleGridByTimeAndLevel", True, False, False),
        ("getNafpAnaEleGridInRectByTimeAndLevel", True, False, True),
        ("getNafpEleGridByTimeAndLevelAndValidtime", False, False, False),
        ("getNafpEleGridInRectByTimeAndLevelAndValidtime", False, False, True),
        ("getNafpEleGridByTimeAndLevelAndValidtimeAndFcstMember", False, True, False),
        (
            "getNafpEleGridInRectByTimeAndLevelAndValidtimeAndFcstMember",
            False,
            True,
            True,
        ),
    ],
)
def test_reviewed_wire_shapes_reach_actual_client_without_inventing_roles(
    nuwe_source, interface, analysis, member, rectangle
):
    from dataclasses import replace
    from reki.translation.nuwe_transport import NuweGridTransport

    source, original, client, http = nuwe_source
    roles = {"time": "time", "level_type": "levelType", "level": "fcstLevel"}
    params = {
        "dataCode": "SYNTHETIC_DATA",
        "fcstEle": "SYNTHETIC_T",
        "time": "20260101080000",
        "levelType": "100",
        "fcstLevel": "850",
    }
    if not analysis:
        roles["step"] = "validTime"
        params["validTime"] = "6"
    if member:
        roles["member"] = "fcstMember"
        params["fcstMember"] = "01"
    if rectangle:
        params.update(minLat="49", maxLat="50", minLon="100", maxLon="101")
    contract = replace(original.contract, interface_id=interface, request_roles=roles)
    adapter = NuweGridTransport(client, contract)
    before = dict(params)
    wrapper = adapter.request(interface, "callAPI_to_gridArray2D", params)
    assert params == before == dict(wrapper["invocation"].parameters)
    assert wrapper["metadata"] == {}
    assert wrapper["data"].shape == (2, 2)
    assert len(http.calls) == 1
    if member:
        assert wrapper["invocation"].parameters["fcstMember"] == "01"
    if analysis:
        assert "validTime" not in http.calls[0]
    adapter.close()
    source.close()
    assert http.closes == 0


@pytest.mark.parametrize("variant", ["analysis", "forecast", "member"])
def test_rectangle_native_request_to_associated_rule_facts_offline(
    nuwe_source, variant
):
    from dataclasses import replace
    from types import SimpleNamespace
    from reki.translation import cmadaas
    from reki.translation.common import value_unit
    from reki.translation.nuwe_transport import NuweGridTransport

    source, original, client, http = nuwe_source
    roles = {"time": "time", "level_type": "levelType", "level": "fcstLevel"}
    interface = "getNafpAnaEleGridInRectByTimeAndLevel"
    params = {
        "dataCode": "SYNTHETIC_DATA",
        "fcstEle": "SYNTHETIC_T",
        "time": "20260101080000",
        "levelType": "100",
        "fcstLevel": "850",
        "minLat": "49.0000",
        "maxLat": "50.0000",
        "minLon": "100.0000",
        "maxLon": "101.0000",
    }
    if variant != "analysis":
        roles["step"] = "validTime"
        params["validTime"] = "6"
        interface = "getNafpEleGridInRectByTimeAndLevelAndValidtime"
    if variant == "member":
        roles["member"] = "fcstMember"
        params["fcstMember"] = "01"
        interface += "AndFcstMember"
    contract = replace(original.contract, interface_id=interface, request_roles=roles)
    adapter = NuweGridTransport(client, contract)
    before = dict(params)
    wrapper = adapter.request(interface, contract.method, params)
    record = cmadaas.associate(contract, params, wrapper, request_index=7)
    assert record.verified and record.request_index == 7
    assert dict(record.parameters) == before == params
    assert all(http.calls[0][key] == str(value) for key, value in before.items())
    with pytest.raises(TypeError):
        record.parameters["minLat"] = "0"
    table = {
        "id": "SYNTHETIC.layers",
        "key_kind": "level_type_and_level",
        "rows": [
            {
                "id": "SYNTHETIC.850",
                "native": {"level_type": "100", "level": "850"},
                "canonical": {"level_type": "pressure", "level": 850},
            }
        ],
    }
    vertical, basis = cmadaas.vertical_table(record, table)
    assert vertical == {"level_type": "pressure", "level": 850, "level_unit": "hPa"}
    assert basis["roles"] == {
        "level_type": "request_association",
        "level": "request_association",
    }
    identity, origins = cmadaas.time_fields(
        record, "Asia/Shanghai", fixed_step="PT0H" if variant == "analysis" else None
    )
    assert identity["time"] == "2026-01-01T00:00:00Z"
    assert identity["step"] == ("PT0S" if variant == "analysis" else "PT21600S")
    assert origins["step"] == (
        "definition" if variant == "analysis" else "request_association"
    )
    if variant == "member":
        members, member_basis = cmadaas.member_field(
            record,
            SimpleNamespace(member_role=lambda _: "perturbation"),
            {
                "id": "SYNTHETIC.members",
                "rows": [
                    {
                        "id": "SYNTHETIC.01",
                        "native": {"code": "01"},
                        "canonical": {"member": 9},
                    }
                ],
            },
        )
        assert members == {"member": 9, "member_role": "perturbation"}
        assert member_basis["rows"] == ["SYNTHETIC.01"]
    requirement = value_unit(wrapper["unit"], "K")
    assert requirement.source == requirement.target == "K"
    np.testing.assert_array_equal(wrapper["data"].values, [[850, 851], [852, 853]])
    assert adapter.retrieval_check["status"] == "pending"
    changed = {**params, "minLat": "48.0000"}
    with pytest.raises(SourceError) as exc:
        cmadaas.associate(contract, changed, wrapper, request_index=8)
    assert exc.value.context["reason"] == "inconsistent_native_metadata"
    assert exc.value.context["request_index"] == 8
    adapter.close()
    adapter.close()
    source.close()
    assert http.closes == 0


@pytest.mark.parametrize("field", ["minLat", "maxLat", "minLon", "maxLon"])
@pytest.mark.parametrize("bad", ["49.00001", 49.00001, "NaN", True])
def test_rectangle_endpoints_reject_unsupported_precision_or_type_before_http(
    nuwe_source, field, bad
):
    from dataclasses import replace
    from reki.translation.nuwe_transport import NuweGridTransport

    source, original, client, http = nuwe_source
    contract = replace(
        original.contract, interface_id="getNafpEleGridInRectByTimeAndLevelAndValidtime"
    )
    adapter = NuweGridTransport(client, contract)
    parameters = {
        "dataCode": "SYNTHETIC_DATA",
        "fcstEle": "SYNTHETIC_T",
        "time": "20260101080000",
        "levelType": "100",
        "fcstLevel": "850",
        "validTime": "6",
        "minLat": "49",
        "maxLat": "50",
        "minLon": "100",
        "maxLon": "101",
        field: bad,
    }
    with pytest.raises(QueryError) as exc:
        adapter.request(contract.interface_id, contract.method, parameters)
    assert exc.value.code == "invalid_config"
    assert exc.value.context["native_field"] == field
    assert not http.calls
    adapter.close()
    source.close()


@pytest.mark.parametrize("field,value", [("minLat", "-90.0001"), ("maxLat", "90.0001")])
def test_rectangle_declared_latitude_limits_are_checked_without_rounding(
    nuwe_source, field, value
):
    from reki.translation.nuwe_wire import GRID_WIRE_PROFILES, validate_parameters

    source, _, _, http = nuwe_source
    params = {
        "dataCode": "SYNTHETIC_DATA",
        "fcstEle": "SYNTHETIC_T",
        "time": "20260101080000",
        "levelType": "100",
        "fcstLevel": "850",
        "validTime": "6",
        "minLat": "49",
        "maxLat": "50",
        "minLon": "100",
        "maxLon": "101",
        field: value,
    }
    with pytest.raises(QueryError) as exc:
        validate_parameters(
            GRID_WIRE_PROFILES["getNafpEleGridInRectByTimeAndLevelAndValidtime"], params
        )
    assert exc.value.context["native_field"] == field
    assert not http.calls
    source.close()


def test_rectangle_query_backend_has_no_unversioned_endpoint_injection(
    nuwe_source, source_factory
):
    from reki.translation.nuwe_transport import NuweGridTransport

    source, _, client, http = nuwe_source
    rectangular, adapter = source_factory(
        owns=True,
        method="callAPI_to_gridArray2D",
        interface_id="getNafpEleGridInRectByTimeAndLevelAndValidtime",
        raw_contract=True,
        transport_factory=lambda contract: NuweGridTransport(client, contract),
    )
    with pytest.raises(QueryError) as exc:
        selected(rectangular).explain()
    assert exc.value.code == "invalid_config"
    assert exc.value.context["reason"] == "missing_context"
    assert set(exc.value.context["missing_fields"]) == {
        "minLat",
        "maxLat",
        "minLon",
        "maxLon",
    }
    assert not http.calls
    rectangular.close()
    source.close()


@pytest.mark.parametrize("alteration", ["extra", "missing", "type"])
def test_controlled_echo_must_match_the_complete_exact_request(nuwe_source, alteration):
    from reki.translation import cmadaas

    source, adapter, _, http = nuwe_source
    params = {
        "dataCode": "SYNTHETIC_DATA",
        "fcstEle": "SYNTHETIC_T",
        "time": "20260101080000",
        "validTime": "6",
        "levelType": "100",
        "fcstLevel": "850",
    }
    echo = dict(params)
    if alteration == "extra":
        echo["minLat"] = "49"
    elif alteration == "missing":
        echo.pop("fcstLevel")
    else:
        echo["fcstLevel"] = 850
    with pytest.raises(SourceError) as exc:
        cmadaas.associate(
            adapter.contract,
            params,
            {
                "record_count": 1,
                "response_kind": "RetGridArray2D",
                "request_parameters": echo,
            },
            request_index=12,
        )
    assert exc.value.context["reason"] == "inconsistent_native_metadata"
    assert exc.value.context["request_index"] == 12 and not http.calls
    source.close()


@pytest.mark.parametrize(
    "interface",
    [
        "getNafpEleGridByTime",
        "getNafpEleGridInRectByTime",
        "getNafpEleGridByTimeAndLevelsAndValidtime",
        "getNafpEleGridInRectByTimeAndLevelAndValidtimeRange",
    ],
)
def test_broad_and_multiple_identity_interfaces_are_not_scalar_grid_contracts(
    nuwe_source, interface
):
    from dataclasses import replace
    from reki.translation.nuwe_transport import NuweGridTransport

    source, adapter, client, http = nuwe_source
    with pytest.raises(QueryError) as exc:
        NuweGridTransport(client, replace(adapter.contract, interface_id=interface))
    assert exc.value.code == "unsupported"
    assert not http.calls
    source.close()


@pytest.mark.parametrize(
    "changes,drop",
    [
        ({}, "fcstLevel"),
        ({}, "validTime"),
        ({"fcstEle": "T,U"}, None),
        ({"fcstLevel": "850,1000"}, None),
        ({"validTime": "0,6"}, None),
        ({"validTime": -1}, None),
        ({"validTime": True}, None),
        ({"time": "20260101"}, None),
        ({"time": "20261301080000"}, None),
        ({"zoomOut": 2}, None),
        ({"eleValueRanges": "T:(0,)"}, None),
        ({"pageNum": 1}, None),
        ({"snapshot": "SYNTHETIC"}, None),
    ],
)
def test_native_wire_inputs_are_bounded_before_any_http(nuwe_source, changes, drop):
    source, adapter, client, http = nuwe_source
    params = {
        "dataCode": "SYNTHETIC_DATA",
        "fcstEle": "SYNTHETIC_T",
        "time": "20260101080000",
        "levelType": "100",
        "fcstLevel": "850",
        "validTime": "6",
    }
    params.update(changes)
    if drop:
        params.pop(drop)
    before = dict(params)
    with pytest.raises(QueryError):
        adapter.request(adapter.contract.interface_id, adapter.contract.method, params)
    assert not http.calls and params == before
    source.close()


@pytest.mark.parametrize(
    "change",
    [
        {"response_roles": {"time": "time"}},
        {
            "request_roles": {
                "time": "time",
                "step": "validTime",
                "level_type": "level_type",
                "level": "fcstLevel",
            }
        },
    ],
)
def test_raw_proto_cannot_claim_response_axes_or_arbitrary_request_bindings(
    nuwe_source, change
):
    from dataclasses import replace
    from reki.translation.nuwe_transport import NuweGridTransport

    source, adapter, client, http = nuwe_source
    with pytest.raises(QueryError) as exc:
        NuweGridTransport(client, replace(adapter.contract, **change))
    assert exc.value.code == "invalid_config"
    assert not http.calls
    source.close()


def test_wire_and_call_success_do_not_prove_business_retrieval_or_snapshot(nuwe_source):
    source, adapter, client, http = nuwe_source
    selection = selected(source)
    before = {
        c["code"]: c["status"]
        for c in selection.explain().analysis["translations"][0]["checks"]
    }
    assert before["complete_retrieval_supported"] == "pending"
    assert not http.calls
    fields = selection.all()
    after = {c["code"]: c["status"] for c in fields.report.translations[0]["checks"]}
    assert after["request_association_verified"] == "passed"
    assert after["complete_retrieval_supported"] == "pending"
    assert fields.report.overall["status"] == "unchecked"
    source.close()


@pytest.mark.parametrize(
    "short", [False, True], ids=["nan-field-exists", "short-grid-fails"]
)
def test_raw_nan_and_incomplete_grid_have_different_presence_boundaries(
    nuwe_source, short
):
    from nuwe_cmadaas.music import apiinterface_pb2 as pb

    source, adapter, client, http = nuwe_source
    message = pb.RetGridArray2D()
    message.latCount, message.lonCount = 2, 2
    message.startLat, message.endLat, message.latStep = 50, 49, -1
    message.startLon, message.endLon, message.lonStep = 100, 101, 1
    message.lats.extend([50, 49])
    message.lons.extend([100, 101])
    message.units = "K"
    message.data.extend([1, 2, 3] if short else [float("nan")] * 4)
    http.content = message.SerializeToString()
    if short:
        with pytest.raises(SourceError) as exc:
            selected(source, levels=(850,)).all()
        assert exc.value.code == "decode_failed"
        assert exc.value.context["request_index"] == 0
        assert "report" not in exc.value.to_dict()
    else:
        fields = selected(source, levels=(850,)).all()
        assert len(fields) == fields.report.overall["field_count"] == 1
        assert np.isnan(fields.to_xarray().t.values).all()
        assert fields.report.overall["status"] == "unchecked"
    source.close()
