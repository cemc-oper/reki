import warnings

import numpy as np
import pytest
import xarray as xr

from reki.core.xarray_contract import (
    DataArrayContractError, DataArrayContractWarning, normalize_data_array,
    validate_data_array,
)


def test_normalize_is_non_mutating_and_idempotent():
    value = xr.DataArray(np.ones((2, 2)), dims=("latitude", "longitude"))
    normalized = normalize_data_array(value, source="memory")
    assert "reki_source" not in value.attrs
    assert normalized.attrs["reki_source"] == "memory"
    assert normalize_data_array(normalized, source="memory").identical(normalized)


def test_validation_warn_raise_and_off_modes():
    value = xr.DataArray([1])
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        issues = validate_data_array(value, mode="warn")
    assert issues[0].code == "missing-units"
    assert issubclass(caught[0].category, DataArrayContractWarning)
    with pytest.raises(DataArrayContractError, match="missing-units"):
        validate_data_array(value, mode="raise")
    assert validate_data_array(value, mode="off") == []
