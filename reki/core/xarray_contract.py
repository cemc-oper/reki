"""Small, non-invasive xarray contract checks used by new integrations."""
from __future__ import annotations
from dataclasses import dataclass
import warnings

@dataclass(frozen=True)
class DataArrayContractIssue:
    code: str
    path: str
    message: str
    severity: str = "warning"

class DataArrayContractWarning(UserWarning):
    pass

class DataArrayContractError(ValueError):
    pass

def normalize_data_array(value, *, source=None):
    """Return a shallow copy with safe provenance metadata, never mutate input."""
    result = value.copy(deep=False)
    if source is not None:
        result.attrs = dict(result.attrs)
        result.attrs.setdefault("reki_source", str(source))
    return result

def validate_data_array(value, *, mode="warn"):
    if mode not in {"off", "warn", "raise"}:
        raise ValueError("mode must be one of: off, warn, raise")
    if mode == "off":
        return []
    issues = []
    if "units" not in value.attrs:
        issues.append(DataArrayContractIssue("missing-units", "attrs.units", "DataArray has no units attribute"))
    for issue in issues:
        if mode == "warn":
            warnings.warn(f"{issue.code}: {issue.message}", DataArrayContractWarning, stacklevel=2)
        else:
            raise DataArrayContractError(f"{issue.code}: {issue.message}")
    return issues
