"""Pure, public CMADaaS model-grid request binding.

This module deliberately does not import the optional CMADaaS client.  It
turns a source-neutral :class:`FieldQuery` plus a stable parameter ID into the
public request fields consumed by the high-level provider path.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping
import re

import pandas as pd

from reki.core import FieldQuery, SourceSpec
from reki.core.source_spec import _freeze, redact
from reki.readers.grib.config import (
    ParameterExternalNameNotMappedError,
    ParameterNamespaceNotFoundError,
    resolve_external_name,
)


class CmadaasRequestError(ValueError):
    """A deterministic pre-network CMADaaS request error."""
    code = "cmadaas_request_error"


class CmadaasNameNotMappedError(CmadaasRequestError):
    code = "cmadaas_name_not_mapped"

    def __init__(self, parameter_id: str):
        self.parameter_id = parameter_id
        super().__init__(f"CMADaaS name is not mapped for parameter {parameter_id!r}")


class CmadaasRequestConflictError(CmadaasRequestError):
    code = "cmadaas_request_conflict"

    def __init__(self, fields: set[str]):
        self.fields = tuple(sorted(fields))
        super().__init__("CMADaaS source kwargs conflict with dynamic request fields: " + ", ".join(self.fields))


def _time(value: Any, label: str) -> pd.Timestamp | pd.Timedelta:
    if value is None:
        raise CmadaasRequestError(f"{label} is required")
    duration = isinstance(value, pd.Timedelta) or (
        isinstance(value, str) and (
            re.fullmatch(r"[+-]?\d+(?:\.\d+)?[A-Za-z]+", value)
            # PlotPlan serializes duration bindings as ISO-8601 so its stable
            # JSON can be passed back to a provider without reinterpretation.
            or re.fullmatch(r"[+-]?P(?:\d+D)?(?:T(?:\d+H)?(?:\d+M)?(?:\d+(?:\.\d+)?S)?)?", value)
        )
    )
    parsed = pd.Timedelta(value) if duration else pd.Timestamp(value)
    if pd.isna(parsed):
        raise CmadaasRequestError(f"{label} must be a valid time")
    return parsed


@dataclass(frozen=True)
class CmadaasRequest:
    """Sanitized immutable model-grid request, with no client configuration."""
    data_code: str
    parameter_id: str
    parameter: str
    level_type: Any = None
    level: Any = None
    start_time: pd.Timestamp | pd.Timedelta | None = None
    forecast_time: pd.Timestamp | pd.Timedelta | None = None
    member: Any = None
    region: Mapping[str, Any] | None = None

    def __post_init__(self):
        for name in ("data_code", "parameter_id", "parameter"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise TypeError(f"{name} must be a non-empty string")
        object.__setattr__(self, "start_time", _time(self.start_time, "start_time"))
        object.__setattr__(self, "forecast_time", _time(self.forecast_time, "forecast_time"))
        object.__setattr__(self, "level_type", _freeze(self.level_type, "level_type"))
        object.__setattr__(self, "level", _freeze(self.level, "level"))
        object.__setattr__(self, "member", _freeze(self.member, "member"))
        if self.region is not None and not isinstance(self.region, Mapping):
            raise TypeError("region must be a mapping or None")
        object.__setattr__(self, "region", None if self.region is None else MappingProxyType(dict(_freeze(self.region, "region"))))

    def to_dict(self) -> dict[str, Any]:
        result = {"data_code": self.data_code, "parameter_id": self.parameter_id,
                  "parameter": self.parameter, "level_type": self.level_type,
                  "level": self.level, "start_time": str(self.start_time),
                  "forecast_time": str(self.forecast_time), "member": self.member}
        if self.region is not None:
            result["region"] = dict(self.region)
        return redact(result)

    def dynamic_source_kwargs(self) -> dict[str, Any]:
        """Return the public fields injected when constructing the source.

        ``data_code`` remains the static DatasetCatalog binding.  The
        parameter, level and time fields are deliberately kept separate so a
        caller cannot accidentally persist them in a source-neutral plan.
        """
        result = {
            "parameter": self.parameter,
            "level_type": self.level_type,
            "level": self.level,
            "start_time": self.start_time,
            "forecast_time": self.forecast_time,
        }
        if self.member is not None:
            result["member"] = self.member
        if self.region is not None:
            result["region"] = dict(self.region)
        return result

    def __repr__(self) -> str:
        return f"CmadaasRequest({self.to_dict()!r})"


def bind_cmadaas_request(source_spec: SourceSpec, *, parameter_id: str, query: FieldQuery,
                         start_time: Any, forecast_time: Any, member: Any = None,
                         region: Mapping[str, Any] | None = None) -> CmadaasRequest:
    """Bind a CMADaaS ``model_grid`` SourceSpec without I/O or client imports."""
    if not isinstance(source_spec, SourceSpec):
        raise TypeError("source_spec must be a SourceSpec")
    if source_spec.name != "cmadaas" or source_spec.kwargs.get("kind") != "model_grid":
        raise CmadaasRequestError("source_spec must be a CMADaaS model_grid source")
    if not isinstance(parameter_id, str) or not parameter_id:
        raise TypeError("parameter_id must be a non-empty string")
    if not isinstance(query, FieldQuery):
        raise TypeError("query must be a FieldQuery")
    dynamic = {"parameter", "level", "level_type", "start_time", "forecast_time", "member", "region"}
    conflict = dynamic.intersection(source_spec.kwargs)
    if conflict:
        raise CmadaasRequestConflictError(conflict)
    data_code = source_spec.kwargs.get("data_code")
    if not isinstance(data_code, str) or not data_code:
        raise CmadaasRequestError("CMADaaS model_grid source requires non-empty data_code")
    if query.step_type is not None or query.time_range is not None:
        raise CmadaasRequestError("CMADaaS model_grid does not support step_type or time_range")
    if member is not None and query.member is not None and member != query.member:
        raise CmadaasRequestConflictError({"member"})
    # v3 records expose a namespaced external-name mapping.  Keeping this
    # lookup here lets v2 remain readable while refusing unsafe guesses.
    try:
        code = resolve_external_name(parameter_id, "cmadaas").code
    except (ParameterExternalNameNotMappedError, ParameterNamespaceNotFoundError) as exc:
        raise CmadaasNameNotMappedError(parameter_id)
    return CmadaasRequest(data_code=data_code, parameter_id=parameter_id, parameter=code,
                          level_type=query.level_type, level=query.level,
                          start_time=start_time, forecast_time=forecast_time,
                          member=query.member if member is None else member, region=region)
