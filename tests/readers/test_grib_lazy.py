"""Tests for GRIB array-level lazy loading (eccodes engine)."""

import pickle

import numpy as np
import pytest
from xarray.core.indexing import LazilyIndexedArray

from reki.core import Source
from reki.readers.grib.eccodes import load_field_from_file
from reki.readers.grib.eccodes import _lazy
from reki.readers.grib.reader import GribReader

LEVELS = [850, 500, 200]


def _is_lazy(data) -> bool:
    return isinstance(data.variable._data, LazilyIndexedArray)


@pytest.fixture
def file_path(grib2_gfs_basic_file_path):
    return grib2_gfs_basic_file_path


class TestSingleLevel:
    def test_values_coords_attrs_identical_to_eager(self, file_path):
        eager = load_field_from_file(
            file_path, "t", level_type="pl", level=850,
        )
        lazy = load_field_from_file(
            file_path, "t", level_type="pl", level=850, lazy=True,
        )
        assert _is_lazy(lazy)
        np.testing.assert_array_equal(lazy.values, eager.values)
        assert list(lazy.coords) == list(eager.coords)
        for coord in eager.coords:
            np.testing.assert_array_equal(
                np.asarray(lazy.coords[coord]), np.asarray(eager.coords[coord]),
            )
        assert lazy.attrs == eager.attrs
        assert lazy.name == eager.name

    def test_indexing_stays_lazy(self, file_path):
        lazy = load_field_from_file(
            file_path, "t", level_type="pl", level=850, lazy=True,
        )
        assert _is_lazy(lazy.isel(latitude=slice(0, 10)))
        assert _is_lazy(lazy.isel(latitude=0, longitude=0))

    def test_default_is_eager(self, file_path):
        data = load_field_from_file(file_path, "t", level_type="pl", level=850)
        assert isinstance(data.variable._data, np.ndarray)

    def test_no_match_returns_none(self, file_path):
        data = load_field_from_file(
            file_path, "no-such-param", level_type="pl", level=850, lazy=True,
        )
        assert data is None

    def test_pickle_roundtrip(self, file_path):
        eager = load_field_from_file(
            file_path, "t", level_type="pl", level=850,
        )
        lazy = load_field_from_file(
            file_path, "t", level_type="pl", level=850, lazy=True,
        )
        restored = pickle.loads(pickle.dumps(lazy))
        np.testing.assert_array_equal(restored.values, eager.values)


class TestMultiLevel:
    def test_values_coords_attrs_identical_to_eager(self, file_path):
        eager = load_field_from_file(
            file_path, "t", level_type="pl", level=LEVELS,
        )
        lazy = load_field_from_file(
            file_path, "t", level_type="pl", level=LEVELS, lazy=True,
        )
        assert _is_lazy(lazy)
        assert lazy.dims == eager.dims
        assert lazy.shape == eager.shape
        np.testing.assert_array_equal(lazy.values, eager.values)
        assert list(lazy.coords) == list(eager.coords)
        for coord in eager.coords:
            np.testing.assert_array_equal(
                np.asarray(lazy.coords[coord]), np.asarray(eager.coords[coord]),
            )
        assert lazy.attrs == eager.attrs

    def test_sel_decodes_one_message(self, file_path, monkeypatch):
        calls = []
        original = _lazy.decode_message_values

        def counting(*args, **kwargs):
            calls.append(1)
            return original(*args, **kwargs)

        monkeypatch.setattr(_lazy, "decode_message_values", counting)

        lazy = load_field_from_file(
            file_path, "t", level_type="pl", level=LEVELS, lazy=True,
        )
        selected = lazy.sel(pl=850)
        assert calls == []
        assert _is_lazy(selected)

        eager = load_field_from_file(
            file_path, "t", level_type="pl", level=LEVELS,
        )
        np.testing.assert_array_equal(
            selected.values, eager.sel(pl=850).values,
        )
        assert len(calls) == 1

    def test_isel_slice_decodes_selected_messages(self, file_path, monkeypatch):
        calls = []
        original = _lazy.decode_message_values

        def counting(*args, **kwargs):
            calls.append(1)
            return original(*args, **kwargs)

        monkeypatch.setattr(_lazy, "decode_message_values", counting)

        lazy = load_field_from_file(
            file_path, "t", level_type="pl", level=LEVELS, lazy=True,
        )
        values = lazy.isel(pl=slice(0, 2)).values
        assert len(calls) == 2

        eager = load_field_from_file(
            file_path, "t", level_type="pl", level=LEVELS,
        )
        np.testing.assert_array_equal(values, eager.isel(pl=slice(0, 2)).values)


class FakeSource(Source):
    pass


class TestGribReader:
    def test_to_xarray_lazy_single_match(self, file_path):
        reader = GribReader(FakeSource(), file_path)
        lazy = reader.to_xarray(
            parameter="t", level_type="pl", level=850, lazy=True,
        )
        eager = reader.to_xarray(parameter="t", level_type="pl", level=850)
        assert _is_lazy(lazy)
        np.testing.assert_array_equal(lazy.values, eager.values)

    def test_to_xarray_lazy_multi_match_stays_lazy(self, file_path):
        reader = GribReader(FakeSource(), file_path)
        dataset = reader.to_xarray(
            parameter="t", level_type="pl", level=LEVELS, lazy=True,
        )
        variable = dataset["t"]
        assert _is_lazy(variable)

        eager = reader.to_xarray(parameter="t", level_type="pl", level=LEVELS)
        np.testing.assert_array_equal(variable.values, eager["t"].values)

    def test_sel_lazy_engine_option(self, file_path):
        reader = GribReader(FakeSource(), file_path)
        lazy = reader.sel(
            parameter="t", level_type="pl", level=850, lazy=True,
        ).to_xarray()
        assert _is_lazy(lazy)

    def test_lazy_no_match_returns_none(self, file_path):
        reader = GribReader(FakeSource(), file_path)
        data = reader.to_xarray(
            parameter="no-such-param", level_type="pl", level=850, lazy=True,
        )
        assert data is None
