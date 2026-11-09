"""Protected NetCDF field selection, retaining xarray's lazy resource lifetime."""
from pathlib import Path
import xarray as xr
from cedarkit_query import QueryError, SourceError
from reki._legacy import reader_errors


def load_field_from_file(file_path, parameter=None, level_type=None, level=None, **kwargs):
    if parameter is not None and not isinstance(parameter, str):
        raise QueryError("invalid_query", "/parameter", "NetCDF parameter must be a variable name")
    engine = kwargs.get("engine")
    if engine is not None and (engine == "cfgrib" or engine not in xr.backends.list_engines()):
        raise QueryError("unsupported", "/engine", "The requested NetCDF backend is unavailable")
    with reader_errors(file_path, "open_netcdf"):
        try:
            dataset = xr.open_dataset(file_path, **kwargs)
        except ValueError as exc:
            raise SourceError("decode_failed", "/source", "NetCDF decoding failed", {"resource": str(file_path)}) from exc
    try:
        if parameter is None:
            parameter = next(iter(dataset.data_vars), None)
        if parameter not in dataset.data_vars:
            raise QueryError("no_match", "/parameter", "NetCDF variable is absent")
        field = dataset[parameter]
        coordinate = level_type or "level"
        if level_type is not None and coordinate not in field.coords:
            raise QueryError("invalid_query", "/level_type", "Explicit NetCDF level coordinate is absent")
        if level is not None:
            if coordinate not in field.coords:
                raise QueryError("no_match", "/level", "NetCDF level coordinate is absent")
            try:
                field = field.sel({coordinate: level})
            except KeyError as exc:
                raise QueryError("no_match", "/level", "NetCDF level is absent") from exc
        field.set_close(dataset.close)
        return field
    except BaseException:
        dataset.close()
        raise


from .reader import NetCDFReader, READER  # noqa: E402
