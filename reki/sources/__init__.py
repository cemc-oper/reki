"""Data sources and the unified entry point ``from_source()``.

A *source* knows where the data comes from. Sources are looked up by name
and combined in three ways, by descending priority (following the design
of ``earthkit.data.core.plugins``):

1. programmatic registration via :func:`register`;
2. ``reki.sources`` entry points declared by external packages;
3. directory scan: a module ``reki/sources/{name}.py`` with a module-level
   ``source`` attribute.
"""

import os
from importlib import import_module
from importlib.metadata import entry_points

from reki.core import Source

__all__ = ["Source", "from_source", "get_source", "register", "SourceMaker"]

#: entry point group used to discover sources from external packages.
ENTRY_POINT_GROUP = "reki.sources"

#: sources registered programmatically via :func:`register`.
REGISTERED = {}


def normalize_name(name: str) -> str:
    """Normalize a source name: underscores and hyphens are interchangeable."""
    return name.replace("_", "-")


def register(name: str, klass) -> None:
    """Register a source class programmatically.

    Parameters
    ----------
    name
        source name used in ``from_source(name, ...)``. Underscores and
        hyphens are interchangeable.
    klass
        the source class. It is instantiated with the arguments passed
        to ``from_source``.
    """
    REGISTERED[normalize_name(name)] = klass


def _load_entry_point_source(name: str):
    """Find a source class from the ``reki.sources`` entry point group."""
    for entry in entry_points(group=ENTRY_POINT_GROUP):
        if normalize_name(entry.name) == name:
            loaded = entry.load()
            if callable(loaded):
                return loaded
            return loaded.source
    return None


def _load_builtin_source(name: str):
    """Find a source class from a built-in ``reki/sources/{name}.py`` module."""
    module_name = name.replace("-", "_")
    module_path = os.path.join(os.path.dirname(__file__), f"{module_name}.py")
    if not os.path.exists(module_path):
        return None
    module = import_module(f".{module_name}", package=__name__)
    return module.source


class SourceMaker:
    """Factory mapping source names to source classes, with caching."""

    SOURCES = {}

    def __call__(self, name: str, *args, **kwargs) -> Source:
        name = normalize_name(name)
        if name not in self.SOURCES:
            klass = (
                REGISTERED.get(name)
                or _load_entry_point_source(name)
                or _load_builtin_source(name)
            )
            if klass is None:
                raise ValueError(f"Unknown source: {name}")
            self.SOURCES[name] = klass

        source = self.SOURCES[name](*args, **kwargs)
        if getattr(source, "name", None) is None:
            source.name = name
        return source

    def __getattr__(self, name: str) -> Source:
        return self(name)


get_source = SourceMaker()


def from_source(name: str, *args, lazily: bool = False, **kwargs) -> Source:
    """Create a source by name and mutate it into the most concrete source.

    The source class is looked up by :data:`SourceMaker`, instantiated
    with ``*args`` and ``**kwargs``, and then ``mutate()`` is called
    repeatedly until the source no longer changes (fixed-point loop).
    For example, ``LocalSource`` mutates into ``FileSource`` once the
    data path is resolved.

    After the loop, ``to_data_object()`` converts the final source into
    the unified data object: for data-bearing sources (e.g. ``file``)
    this is the reader produced by the ``reki.readers`` dispatch; other
    sources (e.g. ``memory``) simply return themselves.

    Parameters
    ----------
    name
        source name, e.g. ``"memory"``. Underscores and hyphens are
        interchangeable.
    *args
        positional arguments passed to the source class.
    lazily
        if True, return a lazy proxy that builds the source on first
        attribute access. Not implemented yet (Phase 7).
    **kwargs
        keyword arguments passed to the source class.

    Returns
    -------
    Source or Reader
        the unified data object.
    """
    if lazily:
        raise NotImplementedError("lazily=True is not implemented yet")

    prev = None
    src = get_source(name, *args, **kwargs)
    while src is not prev:
        prev = src
        src = src.mutate()

    data = src.to_data_object()
    if data is None:
        raise ValueError(f"Source {src} cannot be converted into a data object")
    return data
