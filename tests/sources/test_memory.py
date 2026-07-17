import numpy as np
import pandas as pd
import pytest
import xarray as xr

import reki
from reki.sources.memory import MemorySource


@pytest.fixture
def data_array() -> xr.DataArray:
    return xr.DataArray(
        np.arange(6).reshape(2, 3),
        dims=["y", "x"],
        coords={"y": [0, 1], "x": [10, 20, 30]},
        name="t",
    )


@pytest.fixture
def data_frame() -> pd.DataFrame:
    return pd.DataFrame({"a": [1, 2], "b": [3.0, 4.0]})


def test_module_level_source_variable():
    import reki.sources.memory as memory_module

    assert memory_module.source is MemorySource


def test_unsupported_buffer_type():
    with pytest.raises(TypeError, match="memory source"):
        MemorySource(42)


def test_mutate_returns_self(data_array):
    src = MemorySource(data_array)
    assert src.mutate() is src


def test_data_array(data_array):
    src = MemorySource(data_array)
    assert src.to_xarray() is data_array
    np.testing.assert_array_equal(src.to_numpy(), data_array.values)
    pd.testing.assert_frame_equal(src.to_pandas(), data_array.to_pandas())


def test_dataset(data_array):
    dataset = data_array.to_dataset()
    src = MemorySource(dataset)
    assert src.to_xarray() is dataset
    np.testing.assert_array_equal(src.to_numpy(), dataset.to_array().to_numpy())


def test_data_frame(data_frame):
    src = MemorySource(data_frame)
    assert src.to_pandas() is data_frame
    assert isinstance(src.to_xarray(), xr.Dataset)
    np.testing.assert_array_equal(src.to_numpy(), data_frame.to_numpy())


def test_ndarray_2d():
    buf = np.arange(6).reshape(2, 3)
    src = MemorySource(buf)
    assert src.to_numpy() is buf
    assert isinstance(src.to_xarray(), xr.DataArray)
    pd.testing.assert_frame_equal(src.to_pandas(), pd.DataFrame(buf))


def test_ndarray_1d_to_pandas():
    buf = np.arange(3)
    src = MemorySource(buf)
    pd.testing.assert_series_equal(src.to_pandas(), pd.Series(buf))


def test_ndarray_3d_to_pandas_raises():
    src = MemorySource(np.zeros((2, 2, 2)))
    with pytest.raises(ValueError, match="3-dimensional"):
        src.to_pandas()


def test_from_source_memory(data_array):
    src = reki.from_source("memory", data_array)
    assert isinstance(src, MemorySource)
    assert src.to_xarray() is data_array
