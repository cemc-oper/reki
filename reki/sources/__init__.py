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

from reki.core import Source, SourceSpec

__all__ = [
    "Source",
    "LazySource",
    "from_source",
    "from_source_lazily",
    "get_source",
    "register",
    "SourceMaker",
]

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


class LazySource:
    """Proxy deferring the source pipeline to first attribute access.

    Follows the ``earthkit.data.sources.lazy.LazySource`` pattern: the
    wrapped factory (source construction, the ``mutate()`` fixed-point
    loop and ``to_data_object()``) only runs when an attribute is
    accessed for the first time; the result is cached and all
    attribute access is forwarded to it.

    Instances are created by :func:`from_source` with ``lazily=True``,
    by :func:`from_source_lazily`, or by :func:`from_source` itself
    for sources marked ``remote = True`` (whose pipeline performs
    remote I/O).
    """

    def __init__(self, factory, description: str = ""):
        object.__setattr__(self, "_factory", factory)
        object.__setattr__(self, "_obj", None)
        object.__setattr__(self, "_description", description)

    def _ensure(self):
        """Run the pipeline once and return the final data object."""
        obj = object.__getattribute__(self, "_obj")
        if obj is None:
            obj = object.__getattribute__(self, "_factory")()
            object.__setattr__(self, "_obj", obj)
        return obj

    def __getattr__(self, name: str):
        if name.startswith("__"):
            raise AttributeError(name)
        return getattr(self._ensure(), name)

    def __setattr__(self, name: str, value):
        setattr(self._ensure(), name, value)

    def __repr__(self):
        if object.__getattribute__(self, "_obj") is None:
            return f"LazySource({self._description}, pending)"
        return repr(self._ensure())


def _mutate_and_convert(src: Source):
    """Run the mutate fixed-point loop and convert to the data object."""
    prev = None
    while src is not prev:
        prev = src
        src = src.mutate()

    data = src.to_data_object()
    if data is None:
        raise ValueError(f"Source {src} cannot be converted into a data object")
    return data


def _build(name: str, args, kwargs):
    """Construct a source and run the full pipeline."""
    return _mutate_and_convert(get_source(name, *args, **kwargs))


def _source_arguments(name, args, kwargs):
    """Resolve the public string/SourceSpec forms into one construction form."""
    if not isinstance(name, SourceSpec):
        return name, args, kwargs, str(name)
    if args:
        raise TypeError("SourceSpec cannot be combined with positional arguments")
    merged = dict(name.kwargs)
    merged.update(kwargs)
    return name.name, name.args, merged, repr(name)


def from_source(name: str | SourceSpec, *args, lazily: bool = False, **kwargs) -> Source:
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

    Sources marked ``remote = True`` (e.g. ``url``, ``cmadaas``)
    perform remote I/O in their pipeline; for them ``from_source()``
    returns a :class:`LazySource` proxy so that calling
    ``from_source()`` alone never fires a remote request — the request
    happens on first use (e.g. ``to_xarray()``).

    Parameters
    ----------
    name
        source name, e.g. ``"memory"``. Underscores and hyphens are
        interchangeable.
    *args
        positional arguments passed to the source class.
    lazily
        if True, return a :class:`LazySource` proxy that defers the
        whole pipeline — including source construction — to first
        attribute access.
    **kwargs
        keyword arguments passed to the source class.

    Returns
    -------
    Source or Reader or LazySource
        the unified data object, or a lazy proxy for it.
    """
    is_spec = isinstance(name, SourceSpec)
    name, args, kwargs, description = _source_arguments(name, args, kwargs)
    if lazily:
        # Preserve legacy support for in-memory arbitrary objects (arrays,
        # file handles, ...); SourceSpec deliberately remains serializable.
        return from_source_lazily(SourceSpec(name, args, kwargs) if is_spec else name, *(() if is_spec else args), **({} if is_spec else kwargs))

    src = get_source(name, *args, **kwargs)
    if getattr(src, "remote", False):
        return LazySource(
            lambda: _mutate_and_convert(src),
            description=description,
        )
    return _mutate_and_convert(src)


def from_source_lazily(name: str | SourceSpec, *args, **kwargs) -> LazySource:
    """Lazy variant of :func:`from_source`.

    Returns a :class:`LazySource` proxy; source construction, the
    mutate loop and the conversion to the data object all happen on
    first attribute access, not before.
    """
    name, args, kwargs, description = _source_arguments(name, args, kwargs)
    return LazySource(
        lambda: _build(name, args, kwargs),
        description=f"{description} source (lazily)",
    )
