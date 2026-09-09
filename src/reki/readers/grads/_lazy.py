"""Lazy backend arrays for GrADS binary records.

GrADS data files are raw float32 binaries, so laziness is built on
``np.memmap``: a record's values are read from disk on demand, when
the data is actually accessed. The arrays implement xarray's explicit
indexing protocol and only hold the file path, byte offset and scalar
metadata, so they stay picklable.

Mirrors ``reki.readers.grib.eccodes._lazy``.
"""

from pathlib import Path
from typing import List, Optional, Tuple, Union

import numpy as np
import xarray as xr
from xarray.backends import BackendArray
from xarray.core.indexing import (
    IndexingSupport,
    LazilyIndexedArray,
    explicit_indexing_adapter,
)


def load_record_values(
        path: Union[str, Path],
        offset: int,
        shape: Tuple[int, int],
        dtype: np.dtype,
        flip_y: bool,
) -> np.ndarray:
    """Memory-map one record and return it as an ndarray view.

    The returned array is a ``np.memmap`` (optionally flipped along
    the y axis, which is a view): no data is read until the array is
    actually indexed.
    """
    values = np.memmap(path, dtype=dtype, mode="r", offset=offset, shape=shape)
    if flip_y:
        values = np.flip(values, 0)
    return values


class GradsRecordLazyArray(BackendArray):
    """Lazily read values of a single GrADS record.

    Parameters
    ----------
    path
        path of the GrADS data file. Stored as ``str`` for
        picklability.
    offset
        byte offset of the record in the data file (including the
        4-byte skip for ``sequential`` files).
    shape
        ``(y_count, x_count)`` of the record.
    dtype
        record data type, including endianness (``>f4`` / ``<f4`` /
        ``f4``), same as the eager path.
    flip_y
        whether the y axis is flipped. Eagerly this is applied by
        ``GradsRecordHandler.load_data`` (ctl ``yrev``) and by the
        ``latitude_direction`` option; both are axis-0 flips and are
        combined here into a single net flip.
    """

    def __init__(
            self,
            path: Union[str, Path],
            offset: int,
            shape: Tuple[int, int],
            dtype: np.dtype,
            flip_y: bool,
    ):
        self.path = str(path)
        self.offset = offset
        self.shape = tuple(shape)
        self.dtype = np.dtype(dtype)
        self.flip_y = flip_y

    def __getitem__(self, key):
        return explicit_indexing_adapter(
            key, self.shape, IndexingSupport.BASIC, self._read,
        )

    def _read(self, key) -> np.ndarray:
        values = load_record_values(
            self.path, self.offset, self.shape, self.dtype, self.flip_y,
        )
        return values[key]


class GradsMultiRecordLazyArray(BackendArray):
    """Lazily read values of several GrADS records, stacked on a
    leading level dimension with shape ``(n_levels, y, x)``.

    Only the records selected by the first-dimension index are read.
    """

    def __init__(
            self,
            paths: List[Union[str, Path]],
            offsets: List[int],
            shape: Tuple[int, int, int],
            dtype: np.dtype,
            flip_y: bool,
    ):
        self.paths = [str(p) for p in paths]
        self.offsets = list(offsets)
        self.shape = tuple(shape)
        self.dtype = np.dtype(dtype)
        self.flip_y = flip_y

    def __getitem__(self, key):
        return explicit_indexing_adapter(
            key, self.shape, IndexingSupport.BASIC, self._read,
        )

    def _read(self, key) -> np.ndarray:
        if not isinstance(key, tuple):
            key = (key,)
        key = key + (slice(None),) * (len(self.shape) - len(key))
        level_key, rest_key = key[0], key[1:]

        n_levels = self.shape[0]
        single = isinstance(level_key, (int, np.integer))
        if single:
            indices = [level_key if level_key >= 0 else level_key + n_levels]
        else:
            indices = list(range(*level_key.indices(n_levels)))

        record_shape = self.shape[1:]
        arrays = [
            np.asarray(load_record_values(
                self.paths[i], self.offsets[i], record_shape,
                self.dtype, self.flip_y,
            ))
            for i in indices
        ]
        if single:
            data = arrays[0]
        else:
            data = np.stack(arrays)
        return data[rest_key]


def record_dtype(grads_ctl) -> np.dtype:
    """Record dtype with endianness, mirroring ``load_data``."""
    if grads_ctl.data_endian == "big":
        return np.dtype(">f4")
    if grads_ctl.data_endian == "little":
        return np.dtype("<f4")
    return np.dtype("f4")


def lazy_record_values(record, flip_y: bool) -> LazilyIndexedArray:
    """Wrap one record's lazy values for use as ``DataArray`` data.

    ``record`` is a ``GradsRecordHandler``; ``flip_y`` is the net
    axis-0 flip (ctl ``yrev`` combined with the ``latitude_direction``
    option by the caller).
    """
    grads_ctl = record.grads_ctl
    offset = record.offset
    if "sequential" in grads_ctl.options:
        offset += 4
    return LazilyIndexedArray(
        GradsRecordLazyArray(
            grads_ctl.get_data_file_path(record.record_info),
            offset,
            (grads_ctl.ydef["count"], grads_ctl.xdef["count"]),
            record_dtype(grads_ctl),
            flip_y,
        )
    )


def concat_lazy_arrays(arrays: list, dim_name: str):
    """Concatenate single-record lazy arrays along a new dimension.

    ``xr.concat`` materializes lazy backend arrays, so the records are
    stacked into one ``GradsMultiRecordLazyArray`` instead: only the
    records selected on the new dimension are read. Returns None when
    the arrays are not stackable lazy GrADS arrays (caller falls back
    to ``xr.concat``).
    """
    if not arrays:
        return None

    backends = []
    for array in arrays:
        data = array.variable._data
        if not isinstance(data, LazilyIndexedArray):
            return None
        if not isinstance(data.array, GradsRecordLazyArray):
            return None
        backends.append(data.array)

    first = backends[0]
    for backend in backends:
        if backend.shape != first.shape or backend.flip_y != first.flip_y:
            return None

    template = arrays[0]
    coords = dict(template.coords)
    coords[dim_name] = [a.coords[dim_name].item() for a in arrays]

    return xr.DataArray(
        LazilyIndexedArray(
            GradsMultiRecordLazyArray(
                [b.path for b in backends],
                [b.offset for b in backends],
                (len(arrays),) + first.shape,
                first.dtype,
                first.flip_y,
            )
        ),
        dims=(dim_name,) + tuple(template.dims),
        coords=coords,
        attrs=template.attrs,
        name=template.name,
    )
