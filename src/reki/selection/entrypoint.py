"""Temporary routing boundary until I08 migrates the legacy string callers."""

from collections.abc import Mapping

from .core import from_source as query_source


def from_source(source, *args, **kwargs):
    if isinstance(source, Mapping):
        if args:
            from cedarkit_query import QueryError

            raise QueryError(
                "invalid_config", "/source", "declaration takes no positional arguments"
            )
        return query_source(source, **kwargs)
    # Existing load_field/NetCDF/GrADS/application consumers remain I08 work.
    # This route never accepts the new Query or Request as a second protocol.
    from reki.sources import from_source as legacy_source

    return legacy_source(source, *args, **kwargs)
