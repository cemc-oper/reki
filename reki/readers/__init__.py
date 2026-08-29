"""Format readers and the ``reader()`` dispatch.

A *reader* knows how to parse the data a source provides into a unified
data object. Each reader module (or subpackage) under ``reki/readers/``
may export a ``READER`` factory function with the signature::

    READER(source, path, magic=None, deeper_check=False, **kwargs)

The factory returns a :class:`Reader` instance when it can handle the
file, or ``None`` otherwise. Dispatch follows ``earthkit.data.readers``:

- two-pass probing: all factories are first called with
  ``deeper_check=False`` (quick check, typically on ``magic`` bytes),
  then again with ``deeper_check=True`` (deeper inspection allowed).
  The first factory returning an instance wins;
- a source may name an explicit reader via its ``reader`` attribute
  (a string or a callable), skipping auto-detection;
- when no factory claims the file, an ``UnknownReader`` is returned,
  which keeps the raw bytes and never raises.
"""

import os
from importlib import import_module

from .capabilities import ReaderCapabilities

__all__ = ["Reader", "ReaderCapabilities", "reader", "UnknownReader"]

#: number of bytes read from the head of a file for magic detection.
MAGIC_BYTES = 64

_READERS = {}


class Reader:
    """Base class for all readers.

    A reader is bound to a source and a path and provides conversions
    to unified data objects: ``to_xarray()`` / ``to_pandas()`` /
    ``to_numpy()``.
    """

    def __init__(self, source, path, **kwargs):
        self.source = source
        self.path = str(path)

    @property
    def capabilities(self):
        from .capabilities import ReaderCapabilities
        return ReaderCapabilities()

    def _unsupported(self, operation):
        from reki.core.errors import UnsupportedOperationError
        raise UnsupportedOperationError(self, operation)

    def all(self):
        self._unsupported("all")

    def summary(self):
        self._unsupported("summary")

    def metadata(self, **kwargs):
        self._unsupported("metadata")

    def unique(self, key):
        self._unsupported("unique")

    def head(self, n=5):
        self._unsupported("head")

    def describe(self):
        self._unsupported("describe")

    def ls(self, **kwargs):
        self._unsupported("ls")

    def mutate(self):
        """Give the reader a chance to replace itself after creation."""
        return self

    def mutate_source(self):
        """Give the reader a chance to replace the source, or None."""
        return None

    def to_xarray(self, **kwargs):
        raise NotImplementedError(
            f"{type(self).__name__} does not support to_xarray()"
        )

    def to_pandas(self, **kwargs):
        raise NotImplementedError(
            f"{type(self).__name__} does not support to_pandas()"
        )

    def to_numpy(self, **kwargs):
        raise NotImplementedError(
            f"{type(self).__name__} does not support to_numpy()"
        )


def _load_readers():
    """Scan the ``reki/readers/`` directory for READER factory functions."""
    if _READERS:
        return
    here = os.path.dirname(__file__)
    for path in sorted(os.listdir(here)):
        if path[0] in ("_", "."):
            continue
        name, ext = os.path.splitext(path)
        full = os.path.join(here, path)
        if not (os.path.isdir(full) or ext == ".py"):
            continue
        module = import_module(f".{name}", package=__name__)
        for method in ("READER", "MEMORY_READER", "STREAM_READER"):
            func = getattr(module, method, None)
            if func is not None:
                _READERS[(name, method.lower())] = func


def _readers(method_name="reader"):
    """Return the registered factories for ``method_name`` as {name: func}."""
    _load_readers()
    return {k[0]: v for k, v in _READERS.items() if k[1] == method_name}


def reader(source, path, **kwargs):
    """Create a reader for the file (or directory) at ``path``.

    Parameters
    ----------
    source
        the source the data comes from. If the source has a ``reader``
        attribute, it is used explicitly (a reader name or a callable)
        and auto-detection is skipped.
    path
        path to the local data file.
    **kwargs
        extra keyword arguments passed to the reader factories.

    Returns
    -------
    Reader
        the first reader claiming the file, or ``UnknownReader``.
    """
    explicit = getattr(source, "reader", None)
    if explicit is not None:
        if callable(explicit):
            return explicit(source, path)
        if isinstance(explicit, str):
            name = explicit.replace("-", "_")
            factories = _readers()
            if name not in factories:
                raise ValueError(f"Unknown reader: {explicit}")
            return factories[name](
                source, path, magic=None, deeper_check=False, **kwargs
            )
        raise TypeError(
            f"reader must be a callable or a string, not {type(explicit)}"
        )

    if not os.path.exists(path):
        raise FileNotFoundError(f"No such file: {path}")

    magic = None
    if not os.path.isdir(path):
        with open(path, "rb") as f:
            magic = f.read(MAGIC_BYTES)

    for deeper_check in (False, True):
        for name, factory in _readers().items():
            r = factory(source, path, magic=magic, deeper_check=deeper_check, **kwargs)
            if r is not None:
                return r.mutate()

    from .unknown import UnknownReader

    return UnknownReader(source, path, **kwargs)


def memory_reader(source, buf, **kwargs):
    """Create a reader for an in-memory object.

    Memory readers are factories exported as ``MEMORY_READER`` by reader
    modules, with the signature::

        MEMORY_READER(source, buf, **kwargs)

    The source must name the reader explicitly via its ``reader``
    attribute (a string or a callable); there is no auto-detection for
    in-memory objects.

    Parameters
    ----------
    source
        the source the object comes from. Its ``reader`` attribute
        selects the factory.
    buf
        the in-memory object to read.
    **kwargs
        extra keyword arguments passed to the reader factory.

    Returns
    -------
    Reader
        the reader created by the selected factory.
    """
    explicit = getattr(source, "reader", None)
    if explicit is None:
        raise ValueError(
            "memory sources wrapping an arbitrary object must name "
            "an explicit reader"
        )
    if callable(explicit):
        return explicit(source, buf)
    if isinstance(explicit, str):
        name = explicit.replace("-", "_")
        factories = _readers("memory_reader")
        if name not in factories:
            raise ValueError(f"Unknown memory reader: {explicit}")
        return factories[name](source, buf, **kwargs)
    raise TypeError(
        f"reader must be a callable or a string, not {type(explicit)}"
    )


from .unknown import UnknownReader  # noqa: E402
