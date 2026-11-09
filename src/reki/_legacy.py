"""Shared boundaries for the explicitly protected legacy reading functions."""

from contextlib import contextmanager
import warnings
import inspect

from cedarkit_query import QueryError, SourceError


def check_engine(engine):
    if engine != "eccodes":
        raise QueryError(
            "unsupported", "/engine", "Only the ecCodes GRIB engine is supported"
        )


def ignore_index(value):
    if value is False or value is None:
        return
    if value is not True and not isinstance(value, str):
        raise QueryError(
            "invalid_query", "/with_index", "with_index must be a bool or path string"
        )
    stacklevel = 1
    frame = inspect.currentframe()
    while frame is not None and (
        frame.f_globals.get("__name__") == "reki"
        or frame.f_globals.get("__name__", "").startswith("reki.")
    ):
        stacklevel += 1
        frame = frame.f_back
    del frame
    warnings.warn(
        "GRIB indexes have been retired; remove with_index or set it to False. No index is read or written.",
        FutureWarning,
        stacklevel=stacklevel,
    )


@contextmanager
def reader_errors(resource, operation):
    """Translate known I/O errors only while reki owns the read operation."""
    import eccodes

    context = {"resource": str(resource), "operation": operation}
    try:
        yield
    except FileNotFoundError as exc:
        raise SourceError("resource_not_found", "/source", str(exc), context) from exc
    except PermissionError as exc:
        raise SourceError("permission_denied", "/source", str(exc), context) from exc
    except TimeoutError as exc:
        raise SourceError("timeout", "/source", str(exc), context) from exc
    except OSError as exc:
        raise SourceError("io_error", "/source", str(exc), context) from exc
    except eccodes.CodesInternalError as exc:
        raise SourceError("decode_failed", "/source", str(exc), context) from exc
