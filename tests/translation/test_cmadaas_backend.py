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
    def make(*, owns=False):
        ref = {"id": "SYNTHETIC.single-grid", "version": 1}
        contract = InterfaceContract(
            ref["id"],
            ref["version"],
            "SYNTHETIC.interface",
            "SYNTHETIC.method",
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
        client = Transport()
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
