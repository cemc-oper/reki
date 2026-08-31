import pandas as pd
import pytest

import reki


def source(**kwargs):
    values = {"kind": "model_grid", "data_code": "DEMO"}
    values.update(kwargs)
    return reki.SourceSpec("cmadaas", kwargs=values)


def test_binding_is_pure_and_uses_entry_name_inherited_by_variant():
    request = reki.bind_cmadaas_request(source(), parameter_id="cedarkit.t2m",
                                        query=reki.resolve_parameter("cedarkit.t2m").query,
                                        start_time="2026-01-01T00:00:00", forecast_time=pd.Timedelta("6h"))
    assert request.parameter == "TEM"
    assert request.level_type == "heightAboveGround"
    assert request.level == 2
    assert request.to_dict()["parameter_id"] == "cedarkit.t2m"
    assert request.dynamic_source_kwargs() == {
        "parameter": "TEM", "level_type": "heightAboveGround", "level": 2,
        "start_time": pd.Timestamp("2026-01-01T00:00:00"),
        "forecast_time": pd.Timedelta("6h"),
    }
    capability = reki.source_capability(source())
    assert capability.direct_result is True
    assert capability.metadata_only is False

    with pytest.raises(reki.CmadaasNameNotMappedError) as error:
        reki.bind_cmadaas_request(source(), parameter_id="cedarkit.td", query=reki.FieldQuery(),
                                  start_time="2026-01-01T00:00:00", forecast_time=pd.Timedelta("6h"))
    assert error.value.code == "cmadaas_name_not_mapped"
    assert "DEMO" not in str(error.value)


def test_binding_rejects_static_dynamic_conflict_before_name_lookup():
    with pytest.raises(reki.CmadaasRequestConflictError) as error:
        reki.bind_cmadaas_request(source(level=2), parameter_id="cedarkit.t", query=reki.FieldQuery(),
                                  start_time="2026-01-01", forecast_time="2026-01-01T06:00:00")
    assert error.value.code == "cmadaas_request_conflict"


def test_binding_accepts_plot_plan_iso_duration():
    request = reki.bind_cmadaas_request(
        source(), parameter_id="cedarkit.t2m",
        query=reki.resolve_parameter("cedarkit.t2m").query,
        start_time="2026-01-01T00:00:00Z", forecast_time="P1DT0H0M0S",
    )
    assert request.forecast_time == pd.Timedelta("24h")
