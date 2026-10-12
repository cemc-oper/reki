"""Evidence-limited public grid query execution through CMADaaS model_grid."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import pandas as pd
import xarray as xr

from cedarkit_query import Query, QueryError

from .catalog.query_binding import BindingPlan
from .cmadaas_request import CmadaasRequest, bind_cmadaas_request
from .core import FieldQuery, SourceSpec
from .parameter_adapter import resolve_frozen_parameter
from .sources import from_source
from .sources.cmadaas import CMADAASError


FROZEN_DATA_CODE = "NAFP_FOR_FTM_GRAPES_GFS_25KM_GLB"
FROZEN_REGION = MappingProxyType({
    "type": "rect",
    "start_latitude": 39,
    "end_latitude": 41,
    "start_longitude": 115,
    "end_longitude": 117,
})


@dataclass(frozen=True)
class FrozenCmadaasPlan:
    """Pure request binding; no optional client import or remote availability claim."""

    query: Query
    request: CmadaasRequest
    query_id: str
    binding_id: str
    registry_sha256: str


@dataclass(frozen=True)
class FrozenCmadaasResult:
    """Decoded regional field with the exact request and logical provenance."""

    data: xr.DataArray
    execution: FrozenCmadaasPlan


def plan_frozen_cmadaas(plan: BindingPlan, *, registry_sha256: str) -> FrozenCmadaasPlan:
    """Bind only the four T07/M-05 surface cases to the existing high-level API.

    M-05 used levelType=1/fcstLevel=0 and a fixed Beijing rectangle. The
    provider has no separate statistic-window argument: the 0-24 h window is
    allowed only after T07 has verified the unsuffixed CPE/LPE product code.
    """
    if not isinstance(plan, BindingPlan):
        raise TypeError("plan must be a BindingPlan")
    if plan.binding.kind != "cmadaas" or plan.binding.request_kind != "model_grid":
        raise QueryError("unsupported", "/binding/kind", "frozen execution requires CMADaaS model_grid")
    if plan.binding.data_code != FROZEN_DATA_CODE:
        raise QueryError("unsupported", "/binding/data_code", "data code is outside the frozen evidence")
    resolution = resolve_frozen_parameter(plan.query, registry_sha256=registry_sha256)
    field = resolution.field_query
    if (field.level_type != "surface" or field.level is not None or
            field.extra.get("typeOfFirstFixedSurface") != 1 or field.member is not None):
        raise QueryError("unsupported", "/query/vertical", "frozen surface mapping has changed")
    source = SourceSpec("cmadaas", kwargs={"kind": "model_grid", "data_code": plan.binding.data_code})
    # The public statistic and 0-24 h window were checked above. MUSIC has no
    # statistic parameter; its frozen unsuffixed code selects that product.
    request = bind_cmadaas_request(
        source, parameter_id=resolution.query.parameter,
        query=FieldQuery(level_type=1, level=0),
        start_time=pd.Timestamp(resolution.query.reference_time),
        forecast_time=pd.Timedelta(resolution.query.lead_time),
        region=FROZEN_REGION,
    )
    if request.parameter != resolution.external_code:
        raise QueryError("unsupported", "/query/parameter", "bound CMADaaS code differs from frozen mapping")
    return FrozenCmadaasPlan(resolution.query, request, plan.query_id,
                             plan.binding_id, registry_sha256)


def read_frozen_cmadaas(plan: BindingPlan, *, registry_sha256: str,
                        client: Any = None, config: Any = None) -> FrozenCmadaasResult:
    """Use reki's existing model_grid source; injected clients enable offline tests."""
    execution = plan_frozen_cmadaas(plan, registry_sha256=registry_sha256)
    request = execution.request
    try:
        data = from_source("cmadaas", kind="model_grid", data_code=request.data_code,
                           client=client, config=config, **request.dynamic_source_kwargs()).to_xarray()
    except CMADAASError as exc:
        raise QueryError("provider_error", "/resource", "CMADaaS model_grid request failed",
                         {"service_code": exc.code}) from exc
    except (ValueError, TypeError) as exc:
        raise QueryError("provider_error", "/resource", "CMADaaS response could not be decoded") from exc
    if not isinstance(data, xr.DataArray) or data.dims != ("latitude", "longitude") or 0 in data.shape:
        raise QueryError("provider_error", "/resource", "CMADaaS response is not one populated grid field")
    if data.name != request.parameter:
        raise QueryError("provider_error", "/resource", "CMADaaS response parameter differs from request")
    return FrozenCmadaasResult(data, execution)
