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
  native coordinate grouping).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Dict, List, Optional, Union

import os
import pandas as pd
import xarray as xr

from reki.readers import Reader
from reki.readers.capabilities import ReaderCapabilities
from reki.core import (
    _ReaderQuery, _ReaderMetadata, _ReaderFields, QueryError,
)
from reki.core.field_query import field_query_from_kwargs
from reki.core.source_spec import redact

from .common import fix_level_type
from ._header_metadata import time_metadata_from_message

GRIB_MAGIC = b"GRIB"

#: coordinates that are never the level coordinate of a decoded field.
_NON_LEVEL_COORDS = frozenset(
    {"time", "step", "valid_time", "latitude", "longitude", "number"}
)


def _coerce_query(query):
    if isinstance(query, _ReaderQuery):
        return query
    if isinstance(query, Mapping):
        return field_query_from_kwargs(query)
    raise TypeError("each fetch_many query must be a _ReaderQuery or mapping")


class GribField:
    """A single GRIB field decoded from a file."""

    def __init__(self, data_array: xr.DataArray = None, *, metadata=None, loader=None):
        self._data_array = data_array
        self.metadata = metadata
        self._loader = loader

    def to_xarray(self, **kwargs) -> xr.DataArray:
        if self._data_array is None:
            self._data_array = self._loader(**kwargs)
        return self._data_array

    def to_pandas(self, **kwargs):
        return self.to_xarray(**kwargs).to_pandas()

    def to_numpy(self, **kwargs):
        return self.to_xarray(**kwargs).to_numpy()

    @property
    def values(self):
        return self.to_xarray().values

    def __repr__(self):
        name = self._data_array.name if self._data_array is not None else self.metadata.parameter
        return f"GribField({name!r})"


@dataclass(frozen=True)
class BatchQueryFailure:
    """A per-position query error returned by ``fetch_many(errors='collect')``."""
    position: int
    query: _ReaderQuery
    error: Exception
    match_count: int | None


class GribReader(Reader):
    """Lazy query object for GRIB files.

    Parameters
    ----------
    source
        the source the file comes from.
    path
        path of the GRIB file.
    engine
        decoding engine, only ``"eccodes"``.
    filters
        initial filter conditions, see ``sel()``.
    """

    def __init__(
            self,
            source,
            path,
            engine: str = "eccodes",
            filters: Optional[Dict] = None,
            index_policy: str = "off",
            index_dir=None,
            index_lock_timeout: float = 30.0,
            **kwargs,
    ):
        super().__init__(source, path)
        from reki._legacy import check_engine
        check_engine(engine)
        self.engine = engine
        if index_policy != "off":
            raise QueryError("unsupported", "/index_policy", "GRIB indexes have been retired")
        self.index_policy = index_policy
        self.index_dir = index_dir
        self.index_lock_timeout = index_lock_timeout
        self._query = field_query_from_kwargs(filters or {})

    @property
    def filters(self) -> Dict:
        """The accumulated filter conditions (a copy)."""
        return self._filters_from_query()

    @property
    def capabilities(self):
        return ReaderCapabilities(metadata=self.engine == "eccodes",
                                  field_list=self.engine == "eccodes",
                                  index=False,
                                  fetch_many=self.engine == "eccodes")

    def __repr__(self):
        return (
            f"GribReader({self.path!r}, engine={self.engine!r}, "
            f"filters={redact(self.filters)!r}, index_policy={self.index_policy!r})"
        )

    def sel(
            self,
            query: _ReaderQuery = None,
            /,
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
            (not supported).
        """
        if query is not None and not isinstance(query, _ReaderQuery):
            raise TypeError("the positional argument to sel() must be a _ReaderQuery")
        if query is not None and kwargs:
            raise TypeError("_ReaderQuery and keyword filters cannot be mixed")
        query = query if query is not None else field_query_from_kwargs(kwargs)
        query = self._query.merge(query)
        # Keep the public query representation while constructing a derived
        # reader.  ``_filters_from_query`` is the backend boundary and maps
        # aliases such as ``member`` and ``time_range`` to native GRIB keys;
        # feeding that mapping back through ``field_query_from_kwargs`` would
        # turn those aliases into ``extra`` keys on a chained ``sel()``.
        filters = dict(query.extra)
        for key in ("parameter", "level_type", "level", "step_type", "time_range", "member"):
            value = getattr(query, key)
            if value is not None:
                filters[key] = value
        return GribReader(
            self.source, self.path, engine=self.engine, filters=filters,
            index_policy=self.index_policy, index_dir=self.index_dir,
            index_lock_timeout=self.index_lock_timeout,
        )

    def all(self) -> _ReaderFields:
        """Return all matching fields as lazy references, without decoding values."""
        if self.engine != "eccodes":
            raise NotImplementedError("_ReaderFields is currently available with engine='eccodes' only")
        fields = self._metadata_fields()
        return _ReaderFields(fields, query=self._query, source_summary=self._source_summary(),
                         merge=_merge_arrays)

    def where(self, query=None, /, **kwargs):
        """Return a metadata-only _ReaderFields filtered without expression evaluation."""
        return self.all().where(query, **kwargs)

    def metadata(self, keys=None):
        return self.all().metadata(keys)

    def unique(self, key):
        return self.all().unique(key)

    def head(self, n=5):
        return self.all().head(n)

    def summary(self):
        return self.all().summary()

    def describe(self):
        return self.all().describe()

    def ls(self, keys=None, query=None, /, **kwargs):
        return self.where(query, **kwargs).ls(keys)

    def fetch_many(self, queries, *, cardinality="all", errors="raise"):
        """Experimental batch metadata query.

        All requests share one indexed lookup (or one ecCodes header pass),
        while preserving input order and duplicate requests.
        """
        if self.engine != "eccodes":
            self._unsupported("fetch_many")
        queries = list(queries)
        if errors not in {"raise", "collect"}:
            raise ValueError("errors must be 'raise' or 'collect'")
        if isinstance(cardinality, str):
            cardinalities = [cardinality] * len(queries)
        else:
            cardinalities = list(cardinality)
            if len(cardinalities) != len(queries):
                raise ValueError("cardinality must have one value per query")
        if set(cardinalities) - {"all", "first", "one"}:
            raise ValueError("cardinality must be all, first, or one")
        normalized = [_coerce_query(query) for query in queries]
        cache = {}
        results = []
        # v1 indexes only a fixed metadata subset.  Any arbitrary ecCodes
        # key is evaluated against each header exactly once, rather than
        # incorrectly comparing it with the public metadata projection.
        scanned = self._batch_scan(normalized) if (self._query.extra or any(query.extra for query in normalized)) else None
        fields = None if scanned is not None else self.all()
        for position, (query, mode) in enumerate(zip(normalized, cardinalities)):
            # _ReaderQuery intentionally permits mapping-valued conditions,
            # which are not hashable.  Its bounded canonical repr is stable
            # because construction freezes mappings and sequences.
            key = (repr(query), mode)
            try:
                if key not in cache:
                    selected = scanned[repr(query)] if scanned is not None else fields.where(query)
                    cache[key] = getattr(selected, mode)()
                results.append(cache[key])
            except QueryError as error:
                if errors == "raise":
                    raise
                results.append(BatchQueryFailure(position, query, error, error.context.get("match_count")))
        return results

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
        filters = self._filters_from_query()
        count = filters.pop("count", None)
        if count is not None:
            return self._first_by_count(count)

        level_type = filters.pop("level_type", None)
        parameter = filters.pop("parameter", None)
        level = filters.pop("level", None)

        from .eccodes import load_field_from_file
        data = load_field_from_file(self.path, parameter, level_type, level, **filters)
        return None if data is None else GribField(data)

    def one(self) -> GribField:
        """Return the unique match, raising if the query has zero or many."""
        result = self._unique_field(required=True)
        return result

    def _one_or_none(self) -> Optional[GribField]:
        """Return the unique match, or ``None`` when there is no match."""
        return self._unique_field(required=False)

    def to_xarray(self, lazy: bool = False, **kwargs):
        """Execute the query and decode all matching fields.

        Parameters
        ----------
        lazy
            eccodes engine: defer values decoding to data access
            (see ``load_field_from_file``). May also be given through
            ``sel()`` as an engine option.
        **kwargs
            additional filter conditions (merged with those from
            ``sel()``).

        Returns
        -------
        None
            if no message matches.
        xr.DataArray
            if exactly one message matches.
        xr.Dataset
            if multiple messages match a single hypercube.
        list of xr.Dataset
            if the matches span multiple hypercubes (grouped by level
            type).
        """
        filters = {**self._filters_from_query(), **kwargs}
        count = filters.pop("count", None)
        if count is not None:
            field = self._first_by_count(count)
            return None if field is None else field.to_xarray()

        if self.engine == "eccodes":
            return self._to_xarray_eccodes(filters, lazy=lazy)
        raise QueryError("unsupported", "/engine", "Only ecCodes is supported")

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

    def _filters_from_query(self, query=None) -> Dict:
        def thaw(value):
            if isinstance(value, dict) or hasattr(value, "items"):
                return {k: thaw(v) for k, v in value.items()}
            if isinstance(value, tuple):
                return [thaw(v) for v in value]
            return value
        query = self._query if query is None else query
        filters = thaw(query.extra)
        for key in ("parameter", "level_type", "level", "step_type", "time_range", "member"):
            value = getattr(query, key)
            if value is not None:
                # Existing kernels expect lists, while the public query is immutable.
                filters[key] = thaw(value)
        # _ReaderQuery uses source-neutral names.  GRIB backends retain their
        # native key spellings at this boundary only.
        if "step_type" in filters:
            filters["stepType"] = filters.pop("step_type")
        if "time_range" in filters:
            time_range = pd.Timedelta(filters.pop("time_range"))
            filters["lengthOfTimeRange"] = time_range.total_seconds() / 3600
        if "member" in filters:
            filters["number"] = filters.pop("member")
        return filters

    def _source_summary(self):
        return f"GRIB source {os.path.basename(str(self.path))!r}"

    def _metadata_fields(self):
        """Read valid metadata index or make one scan fallback; no values decode."""
        # v1 deliberately does not index arbitrary _ReaderQuery.extra keys.
        # Verify them against headers rather than turning a valid match into an
        # empty index result.
        if self._query.extra:
            return self._scan_fields()
        return self._scan_fields()

    def _scan_fields(self):
        from .eccodes._scan import iter_headers
        fields = []
        count = self._filters_from_query().get("count")
        for header in iter_headers(self.path, headers_only=True):
            metadata = _metadata_from_message(header.handle, header.ordinal, header.offset, self.path)
            if count is not None:
                matched = header.ordinal + 1 == count
            else:
                matched = self._header_matches(header.handle)
            if matched:
                fields.append(self._field_reference(metadata))
                if count is not None:
                    break
        return fields

    def _batch_scan(self, queries):
        """Evaluate arbitrary-key batch queries in one header iteration."""
        from .eccodes._scan import iter_headers

        unique = {repr(query): query for query in queries}
        matches = {key: [] for key in unique}
        readers = {
            key: self.sel(query) if query != self._query else self
            for key, query in unique.items()
        }
        for header in iter_headers(self.path, headers_only=True):
            metadata = None
            for key, candidate in readers.items():
                if candidate._header_matches(header.handle):
                    if metadata is None:
                        metadata = _metadata_from_message(
                            header.handle, header.ordinal, header.offset, self.path,
                        )
                    matches[key].append(candidate._field_reference(metadata))
        return {
            key: _ReaderFields(values, query=unique[key], source_summary=self._source_summary(),
                           merge=_merge_arrays)
            for key, values in matches.items()
        }

    def _header_matches(self, message):
        from .eccodes._check import _check_message
        from .eccodes._level import _fix_level
        filters = self._filters_from_query()
        parameter = filters.pop("parameter", None)
        level_type = filters.pop("level_type", None)
        level = filters.pop("level", None)
        for option in ("count", "level_dim", "field_name", "show_progress", "lazy", "with_index"):
            filters.pop(option, None)
        fixed_level_type, _ = _fix_level(level_type, None)
        return _check_message(message, parameter, fixed_level_type, level, **filters)

    def _field_reference(self, metadata):
        def loader(**kwargs):
            from .eccodes._decode import load_message_at_offset
            from .eccodes._xarray import create_data_array_from_message
            import eccodes
            message = load_message_at_offset(self.path, metadata.offset)
            if message is None:
                raise ValueError(f"no GRIB message at offset {metadata.offset}")
            try:
                return create_data_array_from_message(message, **kwargs)
            finally:
                eccodes.codes_release(message)
        return GribField(metadata=metadata, loader=loader)

    def _matches_query(self, metadata):
        # Reuse _ReaderFields's public selection semantics for indexed and scanned
        # metadata.  Unknown extra keys deliberately do a header scan fallback.
        query = self._query
        parameter = query.parameter
        if isinstance(parameter, dict):
            if any(metadata.extra.get(key) != value for key, value in parameter.items()):
                return False
        elif parameter is not None and metadata.parameter != parameter:
            return False
        # Query aliases use source-neutral names, whereas an explicit native
        # ecCodes name remains accepted too.
        level_type = query.level_type
        if isinstance(level_type, str) and level_type not in {
                metadata.level_type, _native_level_type(metadata.level_type)}:
            return False
        from reki.core.field_list import _matches
        return _matches(metadata, _ReaderQuery(
            level=query.level, step_type=query.step_type,
            time_range=query.time_range, member=query.member, extra=query.extra,
        ))

    def _unique_field(self, required: bool):
        """Check cardinality from ecCodes headers and decode at most one field."""
        from .eccodes._check import _check_message
        from .eccodes._level import _fix_level
        from .eccodes._scan import iter_headers

        filters = self._filters_from_query()
        count = filters.pop("count", None)
        if count is not None:
            field = self._first_by_count(count)
            if field is None and required:
                raise QueryError("no_match", "", "No fields matched", {"operation": "one", "match_count": 0})
            return field
        parameter = filters.pop("parameter", None)
        level_type = filters.pop("level_type", None)
        level = filters.pop("level", None)
        level_dim = filters.pop("level_dim", None)
        field_name = filters.pop("field_name", None)
        for option in ("level_dim", "field_name", "show_progress", "lazy", "with_index"):
            filters.pop(option, None)
        fixed_level_type, level_dim = _fix_level(level_type, level_dim)
        if field_name is None and isinstance(parameter, str):
            field_name = parameter
        first_found = False
        for header in iter_headers(self.path, headers_only=True):
                if not _check_message(header.handle, parameter, fixed_level_type, level, **filters):
                    continue
                if first_found:
                    raise QueryError("multiple_matches", "", "At least two fields matched", {"operation": "one", "match_count_lower_bound": 2})
                first_found = True
        if not first_found:
            if required:
                raise QueryError("no_match", "", "No fields matched", {"operation": "one", "match_count": 0})
            return None
        # Header handles cannot safely decode values. Re-open only the known
        # unique field after cardinality is proven, so a multiple match never
        # pays a values-decoding cost.
        from .eccodes import load_field_from_file
        data = load_field_from_file(
            self.path, parameter, level_type, level, level_dim=level_dim,
            field_name=field_name, **filters,
        )
        return GribField(data)

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
        from .eccodes._scan import iter_headers
        from reki.readers.grib.common import MISSING_VALUE

        fixed_level_type, _ = _fix_level(level_type, None)

        messages = []
        offsets = []
        for header in iter_headers(self.path, headers_only=True):
            if not _check_message(
                    header.handle, parameter, fixed_level_type, level,
                    **filters,
            ):
                continue
            messages.append(header.detach())
            offsets.append(header.offset)

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



def _merge_arrays(arrays: List[xr.DataArray]):
    """Merge decoded fields by native coordinates."""
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
            # A selected ensemble step has one scalar ``number`` coordinate
            # per field.  Prefer it over the (identical) vertical level so
            # the public xarray result exposes a real member dimension.
            numbers = [array.coords.get("number") for array in arrays_of_name]
            member_values = [None if number is None else number.item() for number in numbers]
            dim_name = level_name
            numbered_members = [value for value in member_values if value is not None]
            if numbered_members and len(set(numbered_members)) == len(numbered_members):
                # ECMWF's deterministic ensemble control has no native GRIB
                # ``number`` key. Reserve public member number 0 for it when
                # merging it with perturbed members into an xarray result.
                arrays_of_name = [
                    array.assign_coords(number=0) if value is None else array
                    for array, value in zip(arrays_of_name, member_values)
                ]
                dim_name = "number"
            # keep lazy GRIB arrays lazy: stack message offsets instead
            # of materializing through xr.concat
            stacked = concat_lazy_arrays(arrays_of_name, dim_name)
            if stacked is not None:
                variables.append(stacked)
            else:
                variables.append(xr.concat(arrays_of_name, dim=dim_name))
        dataset = xr.merge(variables)
        bounds = _layer_bounds(group, level_name)
        if bounds is not None:
            bounds_name = f"{level_name}_bounds"
            dataset = dataset.assign_coords({
                bounds_name: ((level_name, "bounds"), bounds),
            })
            dataset[level_name].attrs["bounds"] = bounds_name
            dataset[bounds_name].attrs["units"] = "m"
        datasets.append(dataset)

    return datasets[0] if len(datasets) == 1 else datasets


def _level_coord_name(data: xr.DataArray) -> Optional[str]:
    for coord in data.coords:
        if coord not in _NON_LEVEL_COORDS:
            return coord
    return None


def _layer_bounds(arrays: List[xr.DataArray], level_name: Optional[str]):
    """Return GRIB layer bounds in merged-level order, when available."""
    if level_name is None:
        return None
    values = []
    for array in arrays:
        top = array.attrs.get("GRIB_topLevel")
        bottom = array.attrs.get("GRIB_bottomLevel")
        if top is None or bottom is None:
            return None
        values.append((array.coords[level_name].item(), top, bottom))
    levels = [value[0] for value in values]
    if len(set(levels)) != len(levels):
        return None
    return [[top, bottom] for _, top, bottom in sorted(values)]


def _metadata_from_message(message, ordinal, offset, path):
    """Extract the safe metadata subset needed before value decoding."""
    import eccodes

    def get(key, default=None):
        try:
            return eccodes.codes_get(message, key)
        except (eccodes.KeyValueNotFoundError, eccodes.WrongTypeError):
            return default

    ni, nj = get("Ni"), get("Nj")
    time_metadata = time_metadata_from_message(message)
    extras = {
        "discipline": get("discipline"),
        "parameterCategory": get("parameterCategory"),
        "parameterNumber": get("parameterNumber"),
        "parameter_match": "short_name",
        "layer_top": get("topLevel"),
        "layer_bottom": get("bottomLevel"),
    }
    # ECMWF IFS writes the ENS control as an ``oper/fc`` message without a
    # native ``number`` key.  Expose it as member 0 so metadata and xarray
    # use the same public control/member convention.
    native_member = get("number")
    member = 0 if native_member is None and get("dataType") == "fc" else native_member
    return _ReaderMetadata(
        index=ordinal, offset=offset, parameter=get("shortName"),
        level_type=_public_level_type(get("typeOfLevel")), level=get("level"),
        start_time=time_metadata["start_time"], step=time_metadata["step"],
        valid_time=time_metadata["valid_time"], step_type=get("stepType"),
        time_range=time_metadata["time_range"], member=member,
        shape=(nj, ni) if ni is not None and nj is not None else None,
        dtype="float64", grid_type=get("gridType"),
        source=os.path.basename(str(path)),
        extra={key: value for key, value in extras.items() if value is not None},
    )


def _public_level_type(value):
    return {"isobaricInhPa": "pl", "surface": "sfc"}.get(value, value)


def _native_level_type(value):
    return {"pl": "isobaricInhPa", "sfc": "surface"}.get(value, value)


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
