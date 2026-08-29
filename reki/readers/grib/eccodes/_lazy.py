"""Lazy backend arrays for GRIB messages (eccodes engine).

The arrays implement xarray's explicit indexing protocol
(``xarray.backends.BackendArray``): they only hold the file path, the
message offset and scalar metadata — never an ecCodes handle — so they
stay picklable (dask distributed safe). Values are decoded from the
GRIB message on ``__getitem__``, i.e. when the data is actually
accessed (``.values``, plotting, writing, ...).

Decoding granularity is a whole GRIB message: the data section is
packed per message and cannot be partially decoded, so slicing happens
after decoding. The point of laziness here is "no access, no decode".

ecCodes is not thread-safe, so every decode is serialized through a
module-level lock.
"""

import threading
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
from ._decode import decode_message_values as _decode_at_offset

#: ecCodes is not thread-safe; serialize all decode calls.
_DECODE_LOCK = threading.Lock()


def decode_message_values(
        path: Union[str, Path],
        offset: int,
        shape: Tuple[int, int],
        missing_value: float,
        fill_value: Optional[float] = np.nan,
) -> np.ndarray:
    """Decode the values of one GRIB message from ``path`` at ``offset``.

    The message is loaded with a short-lived ecCodes handle (opened
    and released inside this function), decoded with the same
    ``missingValue`` semantics as the eager path, and missing points
    are filled with ``fill_value`` (no filling when it is None).
    """
    with _DECODE_LOCK:
        return _decode_at_offset(path, offset, shape, missing_value, fill_value)


class GribLazyArray(BackendArray):
    """Lazily decoded values of a single GRIB message.

    Parameters
    ----------
    path
        path of the GRIB file. Stored as ``str`` for picklability.
    offset
        byte offset of the message in the file (``f.tell()`` before
        the message was read). Decoding seeks to this offset; ecCodes
        scans forward for the ``GRIB`` magic, so padding between the
        offset and the message start is tolerated.
    shape
        ``(nj, ni)`` of the field.
    missing_value
        value ecCodes uses for missing points (set on the message
        before decoding, same as the eager path).
    fill_value
        value replacing missing points after decoding; None disables
        filling.
    """

    def __init__(
            self,
            path: Union[str, Path],
            offset: int,
            shape: Tuple[int, int],
            missing_value: float,
            fill_value: Optional[float] = np.nan,
    ):
        self.path = str(path)
        self.offset = offset
        self.shape = tuple(shape)
        self.dtype = np.dtype(np.float64)
        self.missing_value = missing_value
        self.fill_value = fill_value

    def __getitem__(self, key):
        return explicit_indexing_adapter(
            key, self.shape, IndexingSupport.BASIC, self._decode,
        )

    def _decode(self, key) -> np.ndarray:
        values = decode_message_values(
            self.path, self.offset, self.shape,
            self.missing_value, self.fill_value,
        )
        return values[key]


class GribMultiMessageLazyArray(BackendArray):
    """Lazily decoded values of several GRIB messages, stacked on a
    leading level dimension with shape ``(n_levels, nj, ni)``.

    Only the messages selected by the first-dimension index are
    decoded, so ``da.sel(level=850)`` decodes a single message.
    """

    def __init__(
            self,
            path: Union[str, Path],
            offsets: List[int],
            shape: Tuple[int, int, int],
            missing_value: float,
            fill_value: Optional[float] = np.nan,
    ):
        self.path = str(path)
        self.offsets = list(offsets)
        self.shape = tuple(shape)
        self.dtype = np.dtype(np.float64)
        self.missing_value = missing_value
        self.fill_value = fill_value

    def __getitem__(self, key):
        return explicit_indexing_adapter(
            key, self.shape, IndexingSupport.BASIC, self._decode,
        )

    def _decode(self, key) -> np.ndarray:
        # the explicit indexing adapter hands us a basic key covering
        # all dimensions; pad defensively if it does not.
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

        field_shape = self.shape[1:]
        arrays = [
            decode_message_values(
                self.path, self.offsets[i], field_shape,
                self.missing_value, self.fill_value,
            )
            for i in indices
        ]
        if single:
            data = arrays[0]
        else:
            data = np.stack(arrays)
        return data[rest_key]


def lazy_values(
        path: Union[str, Path],
        offset: int,
        shape: Tuple[int, int],
        missing_value: float,
        fill_value: Optional[float] = np.nan,
) -> LazilyIndexedArray:
    """Wrap one message's lazy values for use as ``DataArray`` data."""
    return LazilyIndexedArray(
        GribLazyArray(path, offset, shape, missing_value, fill_value)
    )


def lazy_multi_values(
        path: Union[str, Path],
        offsets: List[int],
        shape: Tuple[int, int, int],
        missing_value: float,
        fill_value: Optional[float] = np.nan,
) -> LazilyIndexedArray:
    """Wrap several messages' lazy values for use as ``DataArray`` data."""
    return LazilyIndexedArray(
        GribMultiMessageLazyArray(path, offsets, shape, missing_value, fill_value)
    )


def concat_lazy_arrays(arrays: list, dim_name: str):
    """Concatenate single-message lazy arrays along a new dimension.

    ``xr.concat`` materializes lazy backend arrays, so same-file
    ``GribLazyArray`` data is stacked into one
    ``GribMultiMessageLazyArray`` instead: only the messages selected
    on the new dimension are decoded. Coordinates and attributes
    follow the first array, with the new dimension's coordinate taken
    from each array's scalar coord of the same name — mirroring what
    ``xr.concat(arrays, dim_name)`` produces for eager arrays.

    Parameters
    ----------
    arrays
        list of ``xr.DataArray`` whose data wraps ``GribLazyArray``.
    dim_name
        name of the new leading dimension.

    Returns
    -------
    xr.DataArray or None
        the stacked lazy array, or None if the arrays are not
        stackable lazy GRIB arrays (different file, different field
        shape, or not lazy) and the caller should fall back to
        ``xr.concat``.
    """
    if not arrays:
        return None

    backends = []
    for array in arrays:
        data = array.variable._data
        if not isinstance(data, LazilyIndexedArray):
            return None
        if not isinstance(data.array, GribLazyArray):
            return None
        backends.append(data.array)

    first = backends[0]
    for backend in backends:
        if backend.path != first.path or backend.shape != first.shape:
            return None

    template = arrays[0]
    coords = dict(template.coords)
    coords[dim_name] = [a.coords[dim_name].item() for a in arrays]

    return xr.DataArray(
        lazy_multi_values(
            first.path,
            [b.offset for b in backends],
            (len(arrays),) + first.shape,
            first.missing_value,
            first.fill_value,
        ),
        dims=(dim_name,) + tuple(template.dims),
        coords=coords,
        attrs=template.attrs,
        name=template.name,
    )
