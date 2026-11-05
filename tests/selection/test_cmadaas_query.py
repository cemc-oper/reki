"""Public service queries with real client response classes and controlled I/O."""

import json
from pathlib import Path
from urllib.parse import urlencode

import numpy as np
import pytest
import xarray as xr
import yaml
from cedarkit_query import (
    CompletenessError,
    QueryError,
    QueryReport,
    Request,
    SourceError,
)
from nuwe_cmadaas.music import CMADaaSClient, GridArray2D
from nuwe_cmadaas.music.data import RequestInfo
from reki import from_source
from reki.catalog import load_catalog, plan_source_binding
from requests import Timeout

CASES = json.loads(
    (Path(__file__).parent / "fixtures/cmadaas-task07a.json").read_bytes()
)
GFS = next(case for case in CASES if case["id"] == "S-gfs-fcst")
TIME = "2026-08-30T00:00:00Z"
CONTEXT = {"catalog": {"builtin": "reki.catalog.cmadaas.task07a"}}
LIVE_CASES = json.loads(
    (Path(__file__).parent / "fixtures/cmadaas-task07b.json").read_bytes()
)


class ControlledClient:
    def __init__(self, case=GFS, mutate=None):
        self.case, self.mutate = (case, mutate)
        self.calls = []
        self.closes = 0

    def callAPI_to_gridArray2D(self, interface, params):
        self.calls.append((interface, dict(params)))
        values = np.array(self.case["values"], dtype=float)
        result = GridArray2D(
            data=values,
            lat_count=2,
            lon_count=3,
            lats=[39.0, 41.0],
            lons=[115.0, 116.0, 117.0],
            units=self.case["source_unit"],
            user_element_name=params["fcstEle"],
        )
        CMADaaSClient._attach_output_metadata(result, interface, params)
        if self.mutate is not None:
            self.mutate(result, params)
        return result

    def close(self):
        self.closes += 1


@pytest.mark.parametrize("case", LIVE_CASES, ids=lambda c: c["id"])
def test_default_service_resources_bind_the_sixteen_accepted_cases(case):
    def headers(response, params):
        response.user_element_name = f"{params['fcstEle']}_{params['levelType']}"
        response.request.request_params = urlencode(
            {k.lower(): v for k, v in params.items()}
        )
        if case["id"].startswith("S-reps-"):
            response.user_element_name = response.units = ""
            response.request.request_params = ""

    client = ControlledClient(case, mutate=headers)
    with from_source(case["source"], client=client) as source:
        field = source.sel(case["query"]).one(completeness="required")
        (variable,) = field.to_xarray().data_vars
        assert field.to_xarray()[variable].attrs["units"] == case["unit"]
        assert field.report.overall["status"] == "complete"
        assert client.calls == [(case["expected_interface"], case["expected_params"])]
        assert field.metadata["source_unit_basis"] == (
            "mapping" if case["id"].startswith("S-reps-") else "response"
        )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_services_python_and_requests(case, tmp_path):
    client = ControlledClient(case)
    with from_source(case["source"], client=client, context=CONTEXT) as source:
        selected = source.sel(case["query"])
        explanation = selected.explain()
        assert not client.calls
        assert explanation.analysis["expected_count"] == 1
        branch = explanation.analysis["translations"][0]["branches"][0]
        assert branch["backend"] == "cmadaas"
        assert any(b["kind"] == "request_association" for b in branch["basis"])
        field = selected.one(completeness="required")
        ds = field.to_xarray()
        parameter = case["query"]["parameter"]
        name = source.configuration.parameters[parameter]["name"]
        assert ds[name].attrs["cedarkit_parameter_id"] == parameter
        assert ds[name].attrs["units"] == case["unit"]
        assert ds[name].dims == (
            ("time", "step", "member", "height_above_ground", "latitude", "longitude")
            if "member" in case["query"]
            else ("time", "step", "height_above_ground", "latitude", "longitude")
            if parameter == "cedarkit.t2m"
            else ("time", "step", "latitude", "longitude")
        )
        np.testing.assert_array_equal(
            ds[name].values.reshape(2, 3), np.array(case["values"], dtype=float)
        )
        assert client.calls == [(case["expected_interface"], case["expected_params"])]
        assert field.report.overall["status"] == "complete"
        assert field.report.overall["field_count"] == 1
        assert QueryReport.from_json(ds.attrs["cedarkit_query_report"]) == field.report
        checks = field.report.to_dict()["translations"][0]["checks"]
        assert all(check["status"] == "passed" for check in checks)
        if "member" in case["query"]:
            assert ds.member.values.tolist() == [case["query"]["member"]]
            assert ds.member_role.item() == (
                "control" if case["query"]["member"] == 0 else "perturbation"
            )
        expected = ds
    assert client.closes == 0
    for suffix, encode in (("json", json.dumps), ("yaml", yaml.safe_dump)):
        request_path = tmp_path / f"request.{suffix}"
        request_path.write_text(
            encode(
                {
                    "api_version": "cedarkit.request/v1",
                    "source": case["source"],
                    "queries": [case["query"]],
                    "completeness": "required",
                    "context": CONTEXT,
                }
            )
        )
        request = Request.load(request_path)
        with from_source(
            request.source, context=request.context, client=client
        ) as source:
            actual = (
                source.sel(request.queries)
                .one(completeness=request.completeness)
                .to_xarray()
            )
        xr.testing.assert_identical(actual, expected)


def test_repeated_terminal_calls_acquire_again_and_union_deduplicates():
    client = ControlledClient()
    with from_source(GFS["source"], client=client, context=CONTEXT) as source:
        selection = source.sel([GFS["query"], GFS["query"]])
        assert len(selection.all()) == 1
        assert len(client.calls) == 1
        selection.one()
        assert len(client.calls) == 2
        field = selection.one()
        ds = field.to_xarray()
    with pytest.raises(SourceError) as caught:
        field.to_xarray()
    assert caught.value.code == "io_error"
    np.testing.assert_array_equal(
        ds.t2m.values.reshape(2, 3), np.array(GFS["values"], dtype=float)
    )
    assert client.closes == 0


@pytest.mark.parametrize(
    "query",
    [
        {"parameter": "PRE", "time": TIME, "step": "PT24H"},
        {"parameter": "CPE03", "time": TIME, "step": "PT24H"},
        {"parameter": "cedarkit.rainc.any", "time": TIME, "step": "PT12H"},
        {"parameter": "cedarkit.t2m", "time": TIME, "step": "PT1H"},
        {"parameter": "cedarkit.t2m", "step": "PT6H"},
        {
            "parameter": "cedarkit.t2m",
            "time": TIME,
            "step": "PT6H",
            "native": {"grib": {"parameterNumber": 0}},
        },
        {
            "parameter": "cedarkit.t",
            "time": TIME,
            "step": "PT6H",
            "level_type": "pressure",
            "level": 850,
        },
    ],
)
def test_unreviewed_queries_fail_before_io(query):
    client = ControlledClient()
    with (
        from_source(GFS["source"], client=client, context=CONTEXT) as source,
        pytest.raises(QueryError),
    ):
        source.sel(query)
    assert not client.calls


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("time", "20260830060000", "inconsistent_native_metadata"),
        ("level_type", "100", "inconsistent_native_metadata"),
        ("level", "850", "inconsistent_native_metadata"),
        ("valid_time", "12", "inconsistent_native_metadata"),
        ("interface_id", "unrelated", "inconsistent_native_metadata"),
    ],
)
def test_response_request_mismatch_is_an_error(field, value, reason):
    client = ControlledClient(mutate=lambda r, p: r.metadata.update({field: value}))
    with (
        from_source(GFS["source"], client=client, context=CONTEXT) as source,
        pytest.raises(SourceError) as caught,
    ):
        source.sel(GFS["query"]).one()
    assert caught.value.code == "metadata_interpretation_failed"
    assert caught.value.context["reason"] == reason


@pytest.mark.parametrize(
    "mutation,code",
    [
        (lambda r, p: setattr(r, "units", "m"), "metadata_interpretation_failed"),
        (
            lambda r, p: setattr(r, "user_element_name", "GPH"),
            "metadata_interpretation_failed",
        ),
        (lambda r, p: r.metadata.pop("time"), "metadata_interpretation_failed"),
        (lambda r, p: setattr(r, "data", np.arange(5.0)), "incomplete_response"),
        (lambda r, p: setattr(r, "data", np.arange(7.0)), "decode_failed"),
        (
            lambda r, p: setattr(r, "lons", [115, 115, 117]),
            "metadata_interpretation_failed",
        ),
        (lambda r, p: setattr(r, "lats", [20, 21]), "metadata_interpretation_failed"),
        (lambda r, p: setattr(r, "data", np.full((2, 3), np.inf)), "decode_failed"),
    ],
)
def test_invalid_response_is_never_an_empty_result(mutation, code):
    client = ControlledClient(mutate=mutation)
    with (
        from_source(GFS["source"], client=client, context=CONTEXT) as source,
        pytest.raises(SourceError) as caught,
    ):
        source.sel(GFS["query"]).all()
    assert caught.value.code == code


def test_all_nan_field_and_absent_field_are_distinct():
    client = ControlledClient(
        mutate=lambda r, p: setattr(r, "data", np.full((2, 3), np.nan))
    )
    with from_source(GFS["source"], client=client, context=CONTEXT) as source:
        result = source.sel(GFS["query"]).all(completeness="required")
        assert len(result) == 1 and np.isnan(result.to_xarray().t2m).all()

    def empty(result, params):
        result.data = np.empty((0, 0))
        result.lat_count = result.lon_count = 0

    client.mutate = empty
    with from_source(GFS["source"], client=client, context=CONTEXT) as source:
        selected = source.sel(GFS["query"])
        assert len(selected.all()) == 0
        with pytest.raises(CompletenessError) as caught:
            selected.all(completeness="required")
        assert caught.value.code == "missing_fields"
        assert caught.value.report.overall["missing"]
        with pytest.raises(QueryError) as caught:
            selected.one()
        assert caught.value.code == "no_match"


@pytest.mark.parametrize(
    "error,code",
    [
        (1001, "service_error"),
        (-1004, "authentication_failed"),
        (-4001, "permission_denied"),
        (-10003, "decode_failed"),
        (-10001, "timeout"),
    ],
)
def test_service_failures_preserve_the_error_code(error, code):
    cause = Timeout("controlled timeout") if error == -10001 else None
    client = ControlledClient(
        mutate=lambda r, p: setattr(
            r, "request", RequestInfo(error_code=error, cause=cause)
        )
    )
    with (
        from_source(GFS["source"], client=client, context=CONTEXT) as source,
        pytest.raises(SourceError) as caught,
    ):
        source.sel(GFS["query"]).all()
    assert caught.value.code == code
    assert caught.value.context["service_code"] == error
    assert caught.value.__cause__ is cause


def test_owned_client_is_created_only_at_execution_and_closed(monkeypatch, tmp_path):
    import nuwe_cmadaas.music

    config = tmp_path / "synthetic-config.yaml"
    config.write_text("SYNTHETIC CONFIGURATION")
    client, calls = (ControlledClient(), [])
    client.log_policy = "full"

    def create(path, injected):
        calls.append(path)
        return client

    monkeypatch.setattr(nuwe_cmadaas.music, "get_or_create_client", create)
    with from_source(
        {**GFS["source"], "config": str(config)}, context=CONTEXT
    ) as source:
        selected = source.sel(GFS["query"])
        selected.explain()
        assert not calls
        selected.one()
        assert calls == [str(config)]
    assert client.closes == 1
    assert client.log_policy == "summary"


def test_gfs_four_frozen_parameters_share_a_dataset():
    cases = [c for c in CASES if c["id"].startswith("S-GFS-")]

    class Client(ControlledClient):
        def callAPI_to_gridArray2D(self, interface, params):
            self.case = next(c for c in cases if c["code"] == params["fcstEle"])
            return super().callAPI_to_gridArray2D(interface, params)

    client = Client()
    with from_source(GFS["source"], client=client, context=CONTEXT) as source:
        result = source.sel([c["query"] for c in cases]).all(completeness="required")
        ds = result.to_xarray()
        assert set(ds.data_vars) == {"t", "h", "rainc", "rainnc"}
        for case in cases:
            name = source.configuration.parameters[case["query"]["parameter"]]["name"]
            np.testing.assert_array_equal(
                ds[name].values.reshape(2, 3), np.array(case["values"], dtype=float)
            )
            assert ds[name].attrs["units"] == case["unit"]
    assert len(client.calls) == 4


def test_members_and_steps_are_paired_and_sorted():
    case = next(c for c in CASES if c["id"] == "S-geps-pert")

    def distinct(response, params):
        response.data = np.full(
            (2, 3), params["fcstMember"] * 100 + int(params["validTime"])
        )

    client = ControlledClient(case, mutate=distinct)
    with from_source(case["source"], client=client, context=CONTEXT) as source:
        result = source.sel(
            parameter="cedarkit.t2m",
            time=TIME,
            step=["PT12H", "PT6H"],
            member=[30, 2, 1],
        ).all()
        ds = result.to_xarray()
        assert ds.step.values.astype("timedelta64[h]").astype(int).tolist() == [6, 12]
        assert ds.member.values.tolist() == [1, 2, 30]
        assert ds.member_role.values.tolist() == ["perturbation"] * 3
        for member in (1, 2, 30):
            for hour in (6, 12):
                np.testing.assert_array_equal(
                    ds.t2m.sel(member=member, step=np.timedelta64(hour, "h")),
                    member * 100 + hour,
                )
        assert result.report.overall["status"] == "unchecked"
    assert len(client.calls) == 6


def test_member_response_is_checked():
    case = next(c for c in CASES if c["id"] == "S-geps-ctl")
    client = ControlledClient(case, mutate=lambda r, p: r.metadata.update(member=1))
    with (
        from_source(case["source"], client=client, context=CONTEXT) as source,
        pytest.raises(SourceError) as caught,
    ):
        source.sel(case["query"]).one()
    assert caught.value.context["reason"] == "inconsistent_native_metadata"


def test_failed_execution_can_be_retried_without_partial_cache():

    def fail_second(response, params):
        if params["validTime"] == "12":
            response.request.error_code = 1001

    client = ControlledClient(mutate=fail_second)
    with from_source(GFS["source"], client=client, context=CONTEXT) as source:
        selected = source.sel(
            parameter="cedarkit.t2m", time=TIME, step=["PT6H", "PT12H"]
        )
        with pytest.raises(SourceError):
            selected.all()
        assert len(client.calls) == 2
        client.mutate = None
        assert len(selected.all()) == 2
        assert len(client.calls) == 4


def test_first_stops_acquiring_after_its_first_field():
    client = ControlledClient()
    with from_source(GFS["source"], client=client, context=CONTEXT) as source:
        field = source.sel(
            parameter="cedarkit.t2m", time=TIME, step=["PT6H", "PT12H"]
        ).first()
        assert field is not None and len(client.calls) == 1
        assert field.report.overall["status"] == "unchecked"
        branches = field.report.to_dict()["translations"][0]["branches"]
        assert branches[0]["execution"]["status"] == "stopped_early"
        assert branches[1]["execution"]["status"] == "not_started"


def test_unknown_business_domain_fails_required_even_with_a_field():
    client = ControlledClient()
    with (
        from_source(GFS["source"], client=client, context=CONTEXT) as source,
        pytest.raises(CompletenessError) as caught,
    ):
        source.sel(
            parameter="cedarkit.t2m", time="2026-08-31T00:00:00Z", step="PT6H"
        ).all(completeness="required")
    assert caught.value.code == "completeness_undetermined"
    assert caught.value.report.overall["field_count"] == 1


def test_explicit_timezone_offset_uses_utc_contract():
    client = ControlledClient()
    with from_source(GFS["source"], client=client, context=CONTEXT) as source:
        result = source.sel(
            parameter="cedarkit.t2m", time="2026-08-30T08:00:00+08:00", step="PT6H"
        ).one(completeness="required")
        assert result.identity.time == TIME
    assert client.calls[0][1]["time"] == "20260830000000"


@pytest.mark.parametrize(
    "dataset,member",
    [
        ("cma_geps_control_cmadaas", 1),
        ("cma_geps_perturbation_cmadaas", 0),
        ("cma_geps_perturbation_cmadaas", 31),
        ("cma_reps_perturbation_cmadaas", 15),
    ],
)
def test_member_service_boundaries_are_static(dataset, member):
    client = ControlledClient()
    with (
        from_source(
            {"kind": "cmadaas", "dataset": dataset}, client=client, context=CONTEXT
        ) as source,
        pytest.raises(QueryError) as caught,
    ):
        source.sel(parameter="cedarkit.t2m", time=TIME, step="PT6H", member=member)
    assert caught.value.code == "constraint_conflict"
    assert not client.calls


@pytest.mark.parametrize("name", ["TEM", "TEM_103"])
def test_service_element_name_checks_code_and_level_type(name):
    client = ControlledClient(mutate=lambda r, p: setattr(r, "user_element_name", name))
    with from_source(GFS["source"], client=client, context=CONTEXT) as source:
        field = source.sel(GFS["query"]).one()
        assert field.metadata["response_element"] == name


@pytest.mark.parametrize(
    "problem", [None, "wrong_time", "wrong_member", "missing", "duplicate"]
)
def test_server_request_echo_is_checked_independently(problem):
    def change(response, params):
        echoed = {k.lower(): str(v) for k, v in params.items()}
        if problem == "wrong_time":
            echoed["time"] = "20260830060000"
        elif problem == "wrong_member":
            echoed["fcstmember"] = "2"
        elif problem == "missing":
            echoed.pop("fcstele")
        response.request.request_params = urlencode(echoed)
        if problem == "duplicate":
            response.request.request_params += "&time=20260830000000"

    case = next(c for c in CASES if c["id"] == "S-geps-pert")
    with from_source(
        case["source"], client=ControlledClient(case, mutate=change), context=CONTEXT
    ) as source:
        selected = source.sel(case["query"])
        if problem is None:
            field = selected.one()
            assert field.metadata["server_request_echo"]["fcstMember"] == "1"
        else:
            with pytest.raises(SourceError) as caught:
                selected.one()
            assert caught.value.context["reason"] == "inconsistent_native_metadata"


def _reps_context(tmp_path):
    from reki.catalog import load_resource

    catalog = load_resource(CONTEXT["catalog"], "catalog").value.to_dict()
    dataset = next(
        d for d in catalog["datasets"] if d["id"] == "cma_reps_control_cmadaas"
    )
    dataset["products"][0]["sources"][0]["interface_contract"]["id"] = (
        "cmadaas.grid-array2d.reps.member"
    )
    path = tmp_path / "reviewed-reps.json"
    path.write_text(json.dumps(catalog))
    return {"catalog": {"path": str(path)}}


@pytest.mark.parametrize(
    "version,echo,accepted",
    [
        (1, True, False),
        (2, True, True),
        (2, False, False),
        (3, True, True),
        (3, False, False),
    ],
)
def test_mapped_missing_unit_requires_v2_and_verified_server_echo(
    tmp_path, version, echo, accepted
):
    from reki.catalog import load_resource

    catalog = load_resource(CONTEXT["catalog"], "catalog").value.to_dict()
    dataset = next(
        d for d in catalog["datasets"] if d["id"] == GFS["source"]["dataset"]
    )
    dataset["products"][0]["sources"][0]["interface_contract"]["version"] = version
    path = tmp_path / "unit-contract.json"
    path.write_text(json.dumps(catalog))

    def change(response, params):
        response.units = ""
        if echo:
            response.request.request_params = urlencode(
                {k.lower(): v for k, v in params.items()}
            )

    client = ControlledClient(mutate=change)
    with from_source(
        GFS["source"], client=client, context={"catalog": {"path": str(path)}}
    ) as source:
        selection = source.sel(GFS["query"])
        if accepted:
            field = selection.one()
            assert field.metadata["source_unit_basis"] == "mapping"
            assert field.metadata["response_unit"] == ""
            assert field.to_xarray().t2m.attrs["units"] == "K"
        else:
            with pytest.raises(SourceError) as caught:
                selection.one()
            assert caught.value.context["reason"] == "inconsistent_native_metadata"


@pytest.mark.parametrize("reviewed", [False, True])
def test_reps_missing_headers_and_one_cell_overlap_require_reviewed_contract(
    tmp_path, reviewed
):
    case = next(c for c in CASES if c["id"] == "S-reps-ctl")

    def change(response, params):
        response.user_element_name = response.units = ""
        response.lons = [116.95, 116.98, 117.01]

    context = _reps_context(tmp_path) if reviewed else CONTEXT
    with from_source(
        case["source"], client=ControlledClient(case, mutate=change), context=context
    ) as source:
        if reviewed:
            field = source.sel(case["query"]).one()
            assert field.metadata["response_unit"] == ""
            assert field.metadata["source_unit_basis"] == "mapping"
            assert field.to_xarray().t2m.attrs["units"] == "K"
            np.testing.assert_array_equal(
                field.to_xarray().longitude, [116.95, 116.98, 117.01]
            )
        else:
            with pytest.raises(SourceError):
                source.sel(case["query"]).one()


@pytest.mark.parametrize("problem", ["element", "unit", "extent"])
def test_reviewed_reps_contract_still_rejects_conflicting_headers_and_grid(
    tmp_path, problem
):
    case = next(c for c in CASES if c["id"] == "S-reps-ctl")

    def change(response, params):
        if problem == "element":
            response.user_element_name = "TEM_100"
        elif problem == "unit":
            response.units = "m"
        else:
            response.lons = [118.0, 118.03, 118.06]

    with (
        from_source(
            case["source"],
            client=ControlledClient(case, mutate=change),
            context=_reps_context(tmp_path),
        ) as source,
        pytest.raises(SourceError),
    ):
        source.sel(case["query"]).one()


def test_unit_conversion_uses_the_reviewed_response_unit(tmp_path):
    client = ControlledClient()
    config = plan_source_binding(GFS["source"], client=client, context=CONTEXT)
    from reki.catalog import load_resource

    reference = next(
        r["reference"] for r in config.definitions if r["role"] == "parameter_registry"
    )
    parameters = load_resource(reference, "parameters").value.to_dict()
    next(p for p in parameters["parameters"] if p["parameter_id"] == "cedarkit.t")[
        "unit"
    ] = "degC"
    path = tmp_path / "parameters.json"
    path.write_text(json.dumps(parameters))
    with from_source(
        GFS["source"],
        client=client,
        context={**CONTEXT, "parameter_registry": {"path": str(path)}},
    ) as source:
        field = source.sel(GFS["query"]).one()
        assert field.metadata["source_unit"] == "K"
        ds = field.to_xarray()
        assert ds.t2m.attrs["units"] == "degC"
        np.testing.assert_allclose(
            ds.t2m.values.reshape(2, 3), np.array(GFS["values"], dtype=float) - 273.15
        )


def test_analysis_rejects_a_forecast_response():
    case = next(c for c in CASES if c["id"] == "S-gfs-ana")
    client = ControlledClient(
        case, mutate=lambda r, p: r.metadata.update(valid_time="6")
    )
    with (
        from_source(case["source"], client=client, context=CONTEXT) as source,
        pytest.raises(SourceError) as caught,
    ):
        source.sel(case["query"]).all()
    assert caught.value.context["reason"] == "inconsistent_native_metadata"


def test_direct_transport_timeout_is_classified():

    class Client(ControlledClient):
        def callAPI_to_gridArray2D(self, interface, params):
            raise Timeout("controlled timeout")

    with (
        from_source(GFS["source"], client=Client(), context=CONTEXT) as source,
        pytest.raises(SourceError) as caught,
    ):
        source.sel(GFS["query"]).one()
    assert caught.value.code == "timeout"
    assert isinstance(caught.value.__cause__, Timeout)


def test_assembly_requires_compatible_grids():

    def change_grid(response, params):
        if params["validTime"] == "12":
            response.lons = [115.0, 116.5, 117.0]

    with from_source(
        GFS["source"], client=ControlledClient(mutate=change_grid), context=CONTEXT
    ) as source:
        fields = source.sel(
            parameter="cedarkit.t2m", time=TIME, step=["PT6H", "PT12H"]
        ).all()
        assert len(fields) == 2
        with pytest.raises(QueryError) as caught:
            fields.to_xarray()
    assert caught.value.code == "incompatible_grid"


def test_default_catalog_uses_the_verified_service_binding():
    client = ControlledClient()
    with from_source(GFS["source"], client=client) as source:
        selected = source.sel(GFS["query"])
        explanation = selected.explain()
        assert explanation.analysis["translations"][0]["coverage"]["status"] == "passed"
        assert not client.calls
        field = selected.one(completeness="required")
        assert field.to_xarray().t2m.attrs["units"] == "K"
        assert field.report.context["source"]["product_version"] == "service-20261105"


@pytest.mark.parametrize(
    "problem", ["missing_unit", "bad_unit", "table_scope", "rectangle"]
)
def test_invalid_service_mapping_fails_before_io(problem, tmp_path):
    client = ControlledClient()
    config = plan_source_binding(GFS["source"], context=CONTEXT, client=client)
    mappings = config.mappings[0].to_dict()
    row = next(r for r in mappings["mappings"] if r["id"] == "S-gfs-fcst.t2m")
    if problem == "missing_unit":
        row["native"]["translate"]["unit"].pop("config")
    elif problem == "bad_unit":
        row["native"]["translate"]["unit"]["config"]["source_unit"] = "m"
    elif problem == "table_scope":
        mappings["tables"][0]["applies_to"] = {"dataset": "another-dataset"}
    else:
        row["native"]["match"]["minLat"] = 50
    path = tmp_path / "service-mappings.json"
    path.write_text(json.dumps(mappings))
    with (
        from_source(
            GFS["source"],
            client=client,
            context={**CONTEXT, "mappings": {"cmadaas": {"path": str(path)}}},
        ) as source,
        pytest.raises(QueryError),
    ):
        source.sel(GFS["query"])
    assert not client.calls


INSTANT_CASES = json.loads(
    (Path(__file__).parent / "fixtures/cmadaas-task07c.json").read_bytes()
)


@pytest.mark.parametrize("case", INSTANT_CASES, ids=lambda c: c["id"])
def test_instantaneous_service_verticals_and_unit_provenance(case):
    def headers(response, params):
        response.user_element_name = f"{params['fcstEle']}_{params['levelType']}"
        response.request.request_params = urlencode(params)
        if case["query"]["parameter"] == "cedarkit.sweatidx":
            response.units = "Numeric"

    query = dict(case["query"])
    if query.get("level_type") == "pressure":
        query.update(level=85000, level_unit="Pa")
    elif "layer" in query:
        query.pop("layer")
    elif query.get("parameter") == "cedarkit.h.any":
        query.pop("level_type")
    client = ControlledClient(case, mutate=headers)
    with from_source(case["source"], client=client) as source:
        selection = source.sel(query)
        selection.explain()
        assert not client.calls
        field = selection.one(completeness="required")
        dataset = field.to_xarray()
        (name,) = dataset.data_vars
        assert dataset[name].attrs["units"] == case["unit"]
        assert field.report.overall["status"] == "complete"
        assert client.calls == [(case["expected_interface"], case["expected_params"])]
        if "layer" in case["query"]:
            assert field.identity.to_dict()["layer"] == case["query"]["layer"]
            assert (
                field.metadata["vertical_definition"]["id"]
                == "cmadaas.levels.column-layer"
            )
        else:
            assert field.identity.level_type == case["query"]["level_type"]
        assert field.metadata["source_unit_basis"] == (
            "response" if case["source_unit"] or name == "sweatidx" else "mapping"
        )


def test_generic_service_parameter_keeps_vertical_ambiguity_explicit():
    case = next(c for c in INSTANT_CASES if c["query"]["parameter"] == "cedarkit.q")
    query = {
        k: v
        for k, v in case["query"].items()
        if k not in {"level_type", "level", "level_unit"}
    }
    client = ControlledClient(case)
    with from_source(case["source"], client=client) as source:
        with pytest.raises(QueryError) as caught:
            source.sel(query).explain()
        assert caught.value.context["reason"] == "mapping_coverage_gap"
    assert not client.calls


ACCUMULATION_CASES = json.loads(
    (Path(__file__).parent / "fixtures/cmadaas-task07e1.json").read_bytes()
)
MESO1_CASES = json.loads(
    (Path(__file__).parent / "fixtures/cmadaas-task07e2.json").read_bytes()
)


def accumulation_client(case):
    def headers(response, params):
        response.request.request_params = urlencode(params)
        if case["derived_response"]:
            response.request.request_params = response.user_element_name = (
                response.units
            ) = ""
            response.lats = [38.938, 40.938]

    return ControlledClient(case, mutate=headers)


@pytest.mark.parametrize(
    "case", ACCUMULATION_CASES + MESO1_CASES, ids=lambda c: c["id"]
)
def test_reviewed_accumulation_windows_and_instantaneous_identities(case):
    from datetime import datetime, timedelta

    client = accumulation_client(case)
    with from_source(case["source"], client=client) as source:
        selection = source.sel(case["query"])
        selection.explain()
        assert not client.calls
        field = selection.one(completeness="required")
        dataset = field.to_xarray()
        (name,) = dataset.data_vars
        np.testing.assert_array_equal(
            dataset[name].values.reshape(2, 3), case["values"]
        )
        assert dataset[name].attrs["units"] == case["unit"]
        if case.get("code_table"):
            assert field.metadata["code_table"] == case["code_table"]
            assert dataset[name].attrs["code_table"] == case["code_table"]
        assert client.calls == [(case["expected_interface"], case["expected_params"])]
        if case["interval_hours"] is not None:
            time = datetime.fromisoformat(case["query"]["time"])
            assert field.metadata["statistical_interval"] == {
                key: (time + timedelta(hours=hour)).isoformat().replace("+00:00", "Z")
                for key, hour in zip(
                    ("start", "end"), case["interval_hours"], strict=True
                )
            }
        else:
            assert "statistical_interval" not in field.metadata
        if case["derived_response"]:
            assert field.metadata["response_profile"] == "derived_grid"
            assert field.metadata["source_unit_basis"] == "mapping"
            assert field.metadata["response_unit"] == ""
            assert field.metadata["server_request_echo"] == {}
            assert dataset.latitude.values.tolist() == [38.938, 40.938]
        assert field.report.overall["status"] == "complete"


def test_zero_length_service_accumulation_rejects_nonzero_data():
    case = ACCUMULATION_CASES[0]
    client = accumulation_client({**case, "values": [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0]]})
    with from_source(case["source"], client=client) as source:
        with pytest.raises(SourceError) as caught:
            source.sel(case["query"]).one()
        assert caught.value.context["reason"] == "invalid_statistics_metadata"


@pytest.mark.parametrize("problem", ["contract", "period", "equivalent_period"])
def test_derived_profile_and_period_are_explicit_reviewed_contracts(problem, tmp_path):
    case = next(c for c in ACCUMULATION_CASES if c["derived_response"])
    client = accumulation_client(case)
    config = plan_source_binding(case["source"], client=client)
    context = {}
    if problem == "contract":
        catalog = load_catalog().to_dict()
        dataset = next(
            d for d in catalog["datasets"] if d["id"] == case["source"]["dataset"]
        )
        dataset["products"][0]["sources"][0]["interface_contract"]["version"] = 2
        path = tmp_path / "catalog.json"
        path.write_text(json.dumps(catalog))
        context["catalog"] = {"path": str(path)}
    else:
        mappings = config.mappings[0].to_dict()
        row = next(r for r in mappings["mappings"] if r["id"] == case["mapping_id"])
        row["native"]["translate"]["statistics"]["config"]["period"] = {
            "kind": "trailing",
            "duration": "PT6H" if problem == "period" else "PT180M",
        }
        path = tmp_path / "mappings.json"
        path.write_text(json.dumps(mappings))
        context["mappings"] = {"cmadaas": {"path": str(path)}}
    with from_source(case["source"], context=context, client=client) as source:
        if problem == "equivalent_period":
            source.sel(case["query"]).one(completeness="required")
        else:
            with pytest.raises(QueryError) as caught:
                source.sel(case["query"]).explain()
            assert caught.value.code == "invalid_config"
            assert not client.calls


@pytest.mark.parametrize(
    "code", ["rain.since-initialization", "sf.since-initialization"]
)
def test_meso1_analysis_initialization_requires_a_zero_field(code):
    case = next(c for c in MESO1_CASES if c["mapping_id"].endswith(code))
    client = accumulation_client({**case, "values": [[0, 0, 0], [0, 1, 0]]})
    with from_source(case["source"], client=client) as source:
        with pytest.raises(SourceError) as caught:
            source.sel(case["query"]).one()
        assert caught.value.context["reason"] == "invalid_statistics_metadata"


@pytest.mark.parametrize("processed", [False, True])
def test_precipitation_type_rejects_noninteger_codes(processed):
    case = next(
        c for c in MESO1_CASES if c["code_table"] and c["derived_response"] == processed
    )
    client = accumulation_client({**case, "values": [[0, 1, 3], [5, 8, 0.5]]})
    with from_source(case["source"], client=client) as source:
        with pytest.raises(SourceError) as caught:
            source.sel(case["query"]).one()
        assert caught.value.context["reason"] == "inconsistent_native_metadata"


@pytest.mark.parametrize(
    "parameter", ["cedarkit.pwat", "cedarkit.rain.since-initialization"]
)
@pytest.mark.parametrize("problem", ["contract", "profile"])
def test_processed_instantaneous_and_cumulative_grids_require_explicit_v4_review(
    parameter, problem, tmp_path
):
    case = next(
        c
        for c in MESO1_CASES
        if c["derived_response"] and c["query"]["parameter"] == parameter
    )
    client = accumulation_client(case)
    context = {}
    if problem == "contract":
        catalog = load_catalog().to_dict()
        dataset = next(
            d for d in catalog["datasets"] if d["id"] == case["source"]["dataset"]
        )
        dataset["products"][0]["sources"][0]["interface_contract"]["version"] = 3
        path = tmp_path / "catalog.json"
        path.write_text(json.dumps(catalog))
        context["catalog"] = {"path": str(path)}
    else:
        config = plan_source_binding(case["source"], client=client)
        mappings = config.mappings[0].to_dict()
        row = next(r for r in mappings["mappings"] if r["id"] == case["mapping_id"])
        del row["native"]["translate"]["statistics"]["config"]["response_profile"]
        path = tmp_path / "mappings.json"
        path.write_text(json.dumps(mappings))
        context["mappings"] = {"cmadaas": {"path": str(path)}}
    with from_source(case["source"], context=context, client=client) as source:
        if problem == "contract":
            with pytest.raises(QueryError) as caught:
                source.sel(case["query"]).explain()
            assert caught.value.code == "invalid_config"
            assert not client.calls
        else:
            with pytest.raises(SourceError) as caught:
                source.sel(case["query"]).one()
            assert caught.value.context["reason"] == "inconsistent_native_metadata"
