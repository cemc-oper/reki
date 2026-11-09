"""The single public v1 source construction boundary."""
from collections.abc import Mapping
from cedarkit_query import QueryError
from .core import from_source as _from_source


def from_source(source, *args, **kwargs):
    if not isinstance(source, Mapping) or args:
        raise QueryError("invalid_config", "/source", "A source declaration mapping is required")
    return _from_source(source, **kwargs)


__all__ = ["from_source"]
