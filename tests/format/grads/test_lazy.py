"""Tests for GrADS array-level lazy loading (np.memmap backend)."""

import pickle

import numpy as np
import pytest
import xarray as xr
from xarray.core.indexing import LazilyIndexedArray

from reki.readers.grads import _lazy
from reki.readers.grads.field import load_field_from_file

LEVEL_VALUES = [850, 500]


@pytest.fixture
def grads_ctl_path(tmp_path):
    """A tiny synthetic GrADS dataset: one variable, two levels, 3x4."""
    level_1 = np.arange(12, dtype="<f4").reshape(3, 4) + 100.0
    level_2 = np.arange(12, dtype="<f4").reshape(3, 4) + 200.0
    with open(tmp_path / "test.bin", "wb") as f:
        level_1.tofile(f)
        level_2.tofile(f)
    ctl_path = tmp_path / "test.ctl"
    ctl_path.write_text(
        "dset ^test.bin\n"
        "title synthetic test\n"
        "undef -999.0\n"
        "xdef 4 linear 70.0 1.0\n"
        "ydef 3 linear 10.0 1.0\n"
        "zdef 2 levels 850 500\n"
        "tdef 1 linear 00Z01JAN2020 1hr\n"
        "vars 1\n"
        "t 2 99 temperature\n"
        "endvars\n"
    )
    return ctl_path


def _is_lazy(data) -> bool:
    return isinstance(data.variable._data, LazilyIndexedArray)


class TestSingleLevel:
    def test_values_identical_to_eager(self, grads_ctl_path):
        eager = load_field_from_file(
            grads_ctl_path, "t", level=500, latitude_direction="degree_south",
        )
        lazy = load_field_from_file(
            grads_ctl_path, "t", level=500,
            latitude_direction="degree_south", lazy=True,
        )
        assert _is_lazy(lazy)
        np.testing.assert_array_equal(lazy.values, eager.values)
        assert list(lazy.coords) == list(eager.coords)

    def test_indexing_stays_lazy(self, grads_ctl_path):
        lazy = load_field_from_file(
            grads_ctl_path, "t", level=500,
            latitude_direction="degree_south", lazy=True,
        )
        assert _is_lazy(lazy.isel(latitude=slice(0, 2)))

    def test_latitude_flip_identical_to_eager(self, grads_ctl_path):
        eager = load_field_from_file(
            grads_ctl_path, "t", level=500, latitude_direction="degree_north",
        )
        lazy = load_field_from_file(
            grads_ctl_path, "t", level=500,
            latitude_direction="degree_north", lazy=True,
        )
        np.testing.assert_array_equal(lazy.values, eager.values)
        np.testing.assert_array_equal(
            np.asarray(lazy.coords["latitude"]),
            np.asarray(eager.coords["latitude"]),
        )

    def test_pickle_roundtrip(self, grads_ctl_path):
        eager = load_field_from_file(
            grads_ctl_path, "t", level=500, latitude_direction="degree_south",
        )
        lazy = load_field_from_file(
            grads_ctl_path, "t", level=500,
            latitude_direction="degree_south", lazy=True,
        )
        restored = pickle.loads(pickle.dumps(lazy))
        np.testing.assert_array_equal(restored.values, eager.values)


class TestMultiLevel:
    def test_values_coords_identical_to_eager(self, grads_ctl_path):
        eager = load_field_from_file(
            grads_ctl_path, "t", level=LEVEL_VALUES,
            latitude_direction="degree_south",
        )
        lazy = load_field_from_file(
            grads_ctl_path, "t", level=LEVEL_VALUES,
            latitude_direction="degree_south", lazy=True,
        )
        assert _is_lazy(lazy)
        assert lazy.dims == eager.dims
        np.testing.assert_array_equal(lazy.values, eager.values)
        assert list(lazy.coords) == list(eager.coords)

    def test_sel_reads_one_record(self, grads_ctl_path, monkeypatch):
        calls = []
        original = _lazy.load_record_values

        def counting(*args, **kwargs):
            calls.append(1)
            return original(*args, **kwargs)

        monkeypatch.setattr(_lazy, "load_record_values", counting)

        lazy = load_field_from_file(
            grads_ctl_path, "t", level=LEVEL_VALUES,
            latitude_direction="degree_south", lazy=True,
        )
        selected = lazy.sel(level=500.0)
        assert calls == []

        eager = load_field_from_file(
            grads_ctl_path, "t", level=LEVEL_VALUES,
            latitude_direction="degree_south",
        )
        np.testing.assert_array_equal(
            selected.values, eager.sel(level=500.0).values,
        )
        assert len(calls) == 1
