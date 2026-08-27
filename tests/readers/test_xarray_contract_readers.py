"""Offline xarray contract coverage for stage-1 reader families."""
import warnings

import numpy as np
import xarray as xr

from reki.core import DataArrayContractWarning, validate_data_array
from reki.readers.cmadaas import CmadaasReader
from reki.readers.grads.reader import GradsReader
from reki.readers.netcdf.reader import NetCDFReader


def _assert_contract(value):
    if isinstance(value, xr.Dataset):
        value = next(iter(value.data_vars.values()))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        validate_data_array(value, mode="warn")
    assert not [item for item in caught if issubclass(item.category, DataArrayContractWarning)]


def test_netcdf_contract_is_offline(tmp_path):
    expected = xr.Dataset({"temperature": (("latitude", "longitude"), np.ones((2, 2)), {"units": "K"})}, coords={"latitude": [10, 20], "longitude": [100, 110]})
    path = tmp_path / "field.nc"
    expected.to_netcdf(path)
    value = NetCDFReader(None, path).to_xarray()
    _assert_contract(value)
    xr.testing.assert_identical(value, expected)


def test_grads_contract_uses_reader_result_without_io(monkeypatch):
    expected = xr.DataArray([273.15], dims="latitude", attrs={"units": "K"}, name="t")
    monkeypatch.setattr("reki.readers.grads.reader.load_field_from_file", lambda *args, **kwargs: expected)
    value = GradsReader(None, "fixture.ctl").sel(parameter="t", level=850).to_xarray()
    _assert_contract(value)
    assert value.identical(expected)


def test_cmadaas_contract_uses_offline_response_object():
    GridArray2D = type("GridArray2D", (), {})
    response = GridArray2D()
    response.lats, response.lons = [20, 10], [100, 110]
    response.start_lat = response.end_lat = response.start_lon = response.end_lon = 0
    response.lat_count, response.lon_count = 2, 2
    response.data = [1, 2, 3, 4]
    response.units, response.user_element_name = "K", "t"
    value = CmadaasReader(None, response).to_xarray()
    _assert_contract(value)
    assert tuple(value.dims) == ("latitude", "longitude")
    assert value.name == "t"
