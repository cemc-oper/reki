"""GRIB reader: a lazy query object over a GRIB file.

Construction and ``sel()`` do no I/O — they only record the file path
and the filter conditions. The file is scanned when ``first()`` or
``to_xarray()`` is called:

- ``first()``: sequential scan, first match wins (early exit), ``None``
  when nothing matches — identical semantics and performance profile to
  the legacy ``reki.format.grib.load_field_from_file``.
- ``to_xarray()``: a single match gives an ``xr.DataArray``; multiple
  matches are fully scanned and merged by coordinates into an
  ``xr.Dataset`` (or a list of datasets, one per hypercube, following
  the conventions of ``cfgrib.open_datasets``).
"""

from typing import Dict, List, Optional, Union

import os
import xarray as xr

from reki.readers import Reader

from .common import fix_level_type

GRIB_MAGIC = b"GRIB"

#: coordinates that are never the level coordinate of a decoded field.
_NON_LEVEL_COORDS = frozenset(
    {"time", "step", "valid_time", "latitude", "longitude", "number"}
)


class GribField:
    """A single GRIB field decoded from a file."""

    def __init__(self, data_array: xr.DataArray):
        self._data_array = data_array

    def to_xarray(self, **kwargs) -> xr.DataArray:
        return self._data_array

    def to_pandas(self, **kwargs):
        return self._data_array.to_pandas()

    def to_numpy(self, **kwargs):
        return self._data_array.to_numpy()

    @property
    def values(self):
        return self._data_array.values

    def __repr__(self):
        return f"GribField({self._data_array.name!r})"


class GribReader(Reader):
    """Lazy query object for GRIB files.

    Parameters
    ----------
    source
        the source the file comes from.
    path
        path of the GRIB file.
    engine
        decoding engine, ``"eccodes"`` (default) or ``"cfgrib"``.
    filters
        initial filter conditions, see ``sel()``.
    """

    def __init__(
            self,
            source,
            path,
            engine: str = "eccodes",
            filters: Optional[Dict] = None,
            **kwargs,
    ):
        super().__init__(source, path)
        if engine not in ("eccodes", "cfgrib"):
            raise ValueError(f"engine {engine} is not supported")
        self.engine = engine
        self._filters = dict(filters) if filters else {}

    @property
    def filters(self) -> Dict:
        """The accumulated filter conditions (a copy)."""
        return dict(self._filters)

    def __repr__(self):
        return (
            f"GribReader({self.path!r}, engine={self.engine!r}, "
            f"filters={self._filters!r})"
        )

    def sel(
            self,
            parameter: Union[str, Dict] = None,
            level_type: Union[str, Dict, List] = None,
            level: Union[int, float, List, Dict, str] = None,
            count: int = None,
            **kwargs,
    ) -> "GribReader":
        """Return a new query object with more filter conditions (no I/O).

        Parameters
        ----------
        parameter
            parameter name (shortName) or a dict of GRIB keys.
        level_type
            level type, e.g. "pl", "sfc", "isobaricInhPa", or a dict of
            GRIB keys.
        level
            level value(s). A list (e.g. ``[850, 500]``) matches
            multiple messages.
        count
            1-based message index in the file; when set, all other
            conditions are ignored (eccodes engine only).
        **kwargs
            extra GRIB keys used as filter conditions (eccodes engine),
            and engine options: ``level_dim``, ``field_name``,
            ``show_progress``, ``lazy`` (eccodes), ``with_index``
            (cfgrib).
        """
        filters = dict(self._filters)
        for key, value in (
                ("parameter", parameter),
                ("level_type", level_type),
                ("level", level),
                ("count", count),
        ):
            if value is not None:
                filters[key] = value
        filters.update(kwargs)
        return GribReader(
            self.source, self.path, engine=self.engine, filters=filters
        )

    def first(self) -> Optional[GribField]:
        """Scan sequentially and return the first matching field.

        The filter conditions are passed to the engine kernel unchanged
        (each engine applies its own level type fixing), so the result
        is identical to calling the kernel's ``load_field_from_file``.

        Returns
        -------
        GribField or None
            the first matching field (file order), or None if not found.
        """
        filters = dict(self._filters)
        count = filters.pop("count", None)
        if count is not None:
            return self._first_by_count(count)

        level_type = filters.pop("level_type", None)
        parameter = filters.pop("parameter", None)
        level = filters.pop("level", None)

        if self.engine == "eccodes":
            from .eccodes import load_field_from_file
        else:
            from .cfgrib import load_field_from_file

        data = load_field_from_file(
            self.path, parameter, level_type, level, **filters
        )
        return None if data is None else GribField(data)

    def to_xarray(self, lazy: bool = False, **kwargs):
        """Execute the query and decode all matching fields.

        Parameters
        ----------
        lazy
            eccodes engine: defer values decoding to data access
            (see ``load_field_from_file``). May also be given through
            ``sel()`` as an engine option. The cfgrib engine reads
            through its on-disk index on demand by nature and ignores
            this option.
        **kwargs
            additional filter conditions (merged with those from
            ``sel()``).

        Returns
        -------
        None
            if no message matches (eccodes engine; the cfgrib engine
            follows cfgrib/xarray behaviour for empty filters).
        xr.DataArray
            if exactly one message matches.
        xr.Dataset
            if multiple messages match a single hypercube.
        list of xr.Dataset
            if the matches span multiple hypercubes (grouped by level
            type, following ``cfgrib.open_datasets``).
        """
        filters = {**self._filters, **kwargs}
        count = filters.pop("count", None)
        if count is not None:
            field = self._first_by_count(count)
            return None if field is None else field.to_xarray()

        if self.engine == "eccodes":
            return self._to_xarray_eccodes(filters, lazy=lazy)
        return self._to_xarray_cfgrib(filters)

    def __len__(self):
        raise NotImplementedError(
            "len() requires the GRIB metadata index, which is planned "
            "for a later phase; use first() / to_xarray() instead"
        )

    def __getitem__(self, item):
        raise NotImplementedError(
            "positional access requires the GRIB metadata index, which is "
            "planned for a later phase; use sel() / first() instead"
        )

    # ------------------------------------------------------------------
    # internals

    def _first_by_count(self, count: int) -> Optional[GribField]:
        if self.engine != "eccodes":
            raise NotImplementedError(
                "count is only supported with the eccodes engine"
            )
        import eccodes

        from .eccodes import load_message_from_file
        from .eccodes._xarray import create_data_array_from_message

        message = load_message_from_file(self.path, count=count)
        if message is None:
            return None
        data = create_data_array_from_message(message)
        eccodes.codes_release(message)
        return GribField(data)

    def _to_xarray_eccodes(self, filters: Dict, lazy: bool = False):
        import eccodes

        from .eccodes import load_messages_from_file
        from .eccodes._level import _fix_level
        from .eccodes._xarray import (
            create_data_array_from_message,
        )

        filters = dict(filters)
        parameter = filters.pop("parameter", None)
        level_type = filters.pop("level_type", None)
        level = filters.pop("level", None)
        level_dim = filters.pop("level_dim", None)
        field_name = filters.pop("field_name", None)
        filters.pop("show_progress", None)
        filters.pop("with_index", None)
        lazy = filters.pop("lazy", lazy)
        # remaining keys are extra GRIB keys used as filter conditions

        if field_name is None and isinstance(parameter, str):
            field_name = parameter

        _, fixed_level_dim = _fix_level(level_type, level_dim)

        if lazy:
            arrays = self._scan_lazy_arrays(
                parameter, level_type, level, fixed_level_dim, field_name,
                filters,
            )
            if arrays is None:
                return None
            return _merge_arrays(arrays)

        messages = load_messages_from_file(
            self.path, parameter, level_type, level, **filters
        )
        if messages is None:
            return None

        try:
            arrays = [
                create_data_array_from_message(
                    message,
                    level_dim_name=fixed_level_dim,
                    field_name=field_name,
                )
                for message in messages
            ]
        finally:
            for message in messages:
                eccodes.codes_release(message)

        return _merge_arrays(arrays)

    def _scan_lazy_arrays(
            self,
            parameter,
            level_type,
            level,
            fixed_level_dim,
            field_name,
            filters: Dict,
    ) -> Optional[List[xr.DataArray]]:
        """Scan with ``headers_only=True`` and build lazy arrays.

        Mirrors ``load_messages_from_file`` but skips message data
        sections and records message offsets, so values decoding is
        deferred to data access.
        """
        import eccodes
        import numpy as np

        from .eccodes._check import _check_message
        from .eccodes._lazy import lazy_values
        from .eccodes._level import _fix_level
        from .eccodes._xarray import create_data_array_from_message
        from reki.readers.grib.common import MISSING_VALUE
        from reki.readers.grib.common._parameter import convert_parameter

        fixed_level_type, _ = _fix_level(level_type, None)
        converted_parameter = convert_parameter(parameter)

        messages = []
        offsets = []
        with open(self.path, "rb") as f:
            while True:
                offset = f.tell()
                message = eccodes.codes_grib_new_from_file(f, headers_only=True)
                if message is None:
                    break
                if not _check_message(
                        message, converted_parameter, fixed_level_type, level,
                        **filters,
                ):
                    eccodes.codes_release(message)
                    continue
                messages.append(message)
                offsets.append(offset)

        if not messages:
            return None

        try:
            arrays = [
                create_data_array_from_message(
                    message,
                    level_dim_name=fixed_level_dim,
                    field_name=field_name,
                    values=lazy_values(
                        self.path,
                        offset,
                        (
                            eccodes.codes_get(message, "Nj"),
                            eccodes.codes_get(message, "Ni"),
                        ),
                        MISSING_VALUE,
                        np.nan,
                    ),
                )
                for message, offset in zip(messages, offsets)
            ]
        finally:
            for message in messages:
                eccodes.codes_release(message)
        return arrays

    def _to_xarray_cfgrib(self, filters: Dict):
        import cfgrib

        from .cfgrib._util import (
            _fill_index_path,
            _fill_level_type,
            _fill_level_value,
            _fill_parameter,
        )

        filters = dict(filters)
        parameter = filters.pop("parameter", None)
        level_type = filters.pop("level_type", None)
        level = filters.pop("level", None)
        with_index = filters.pop("with_index", False)
        for option in ("level_dim", "field_name", "show_progress", "lazy"):
            filters.pop(option, None)
        # remaining keys are extra GRIB keys used as filter conditions

        filter_by_keys = dict(filters)
        read_keys = []

        if parameter is not None:
            _fill_parameter(parameter, filter_by_keys, read_keys)
        if level_type is not None:
            level_type = fix_level_type(level_type, engine="cfgrib")
            _fill_level_type(level_type, filter_by_keys, read_keys)
        if level is not None and level != "all":
            if isinstance(level, list):
                filter_by_keys["level"] = level
            else:
                _fill_level_value(level, filter_by_keys, read_keys)

        backend_kwargs = {"filter_by_keys": filter_by_keys}
        if len(read_keys) > 0:
            backend_kwargs["read_keys"] = read_keys
        _fill_index_path(with_index, backend_kwargs)

        # cfgrib.open_datasets groups incompatible hypercubes into
        # separate datasets (xarray no longer provides open_datasets).
        datasets = cfgrib.open_datasets(
            self.path, backend_kwargs=backend_kwargs
        )
        # an empty filter result yields a single empty dataset
        datasets = [ds for ds in datasets if ds.data_vars or ds.dims]
        if not datasets:
            return None
        if len(datasets) > 1:
            return datasets

        data_set = datasets[0]
        if len(data_set.data_vars) == 1:
            data = data_set[list(data_set.data_vars)[0]]
            if data.ndim <= 2:
                return data
        return data_set


def _merge_arrays(arrays: List[xr.DataArray]):
    """Merge decoded fields following cfgrib/xarray conventions."""
    from .eccodes._lazy import concat_lazy_arrays

    if not arrays:
        return None
    if len(arrays) == 1:
        return arrays[0]

    groups: Dict[Optional[str], List[xr.DataArray]] = {}
    for array in arrays:
        groups.setdefault(_level_coord_name(array), []).append(array)

    datasets = []
    for level_name, group in groups.items():
        by_name: Dict[str, List[xr.DataArray]] = {}
        for array in group:
            by_name.setdefault(array.name, []).append(array)
        variables = []
        for arrays_of_name in by_name.values():
            if len(arrays_of_name) == 1:
                variables.append(arrays_of_name[0])
                continue
            # keep lazy GRIB arrays lazy: stack message offsets instead
            # of materializing through xr.concat
            stacked = concat_lazy_arrays(arrays_of_name, level_name)
            if stacked is not None:
                variables.append(stacked)
            else:
                variables.append(xr.concat(arrays_of_name, dim=level_name))
        datasets.append(xr.merge(variables))

    return datasets[0] if len(datasets) == 1 else datasets


def _level_coord_name(data: xr.DataArray) -> Optional[str]:
    for coord in data.coords:
        if coord not in _NON_LEVEL_COORDS:
            return coord
    return None


def READER(source, path, magic=None, deeper_check=False, **kwargs):
    """Claim files starting with the GRIB indicator section.

    When the reader is explicitly named (``magic`` is None), the file
    is trusted to be GRIB.
    """
    if os.path.isdir(path):
        return None
    if magic is None:
        return GribReader(source, path, **kwargs)
    if len(magic) < len(GRIB_MAGIC) or magic[: len(GRIB_MAGIC)] != GRIB_MAGIC:
        return None
    return GribReader(source, path, **kwargs)
