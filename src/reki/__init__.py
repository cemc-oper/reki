from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("reki")
except PackageNotFoundError:
    # package is not installed
    pass

# Keep configuration imports independent of readers and optional clients.
from importlib import import_module

_EXPORTS = {
    "from_source": (".selection.entrypoint", "from_source"),
    "Query": ("cedarkit_query", "Query"),
    "Request": ("cedarkit_query", "Request"),
    "QueryError": ("cedarkit_query", "QueryError"),
    "SourceError": ("cedarkit_query", "SourceError"),
    "CompletenessError": ("cedarkit_query", "CompletenessError"),
    "QueryReport": ("cedarkit_query", "QueryReport"),
    "QueryExplanation": ("cedarkit_query", "QueryExplanation"),
    "from_source_lazily": (".sources", "from_source_lazily"),
    "register": (".sources", "register"),
    "source_capability": (".sources", "source_capability"),
    "Source": (".sources", "Source"),
    "ReaderCapabilities": (".readers", "ReaderCapabilities"),
    "SourceSpec": (".core", "SourceSpec"),
    "FieldQuery": (".core", "FieldQuery"),
    "FieldMetadata": (".core", "FieldMetadata"),
    "FieldList": (".core", "FieldList"),
    "DataNotFoundError": (".core", "DataNotFoundError"),
    "MultipleFieldsMatchedError": (".core", "MultipleFieldsMatchedError"),
    "UnsupportedOperationError": (".core", "UnsupportedOperationError"),
    "normalize_data_array": (".core", "normalize_data_array"),
    "validate_data_array": (".core", "validate_data_array"),
    "load_catalog": (".catalog", "load_catalog"),
    "operator": (".operator", None),
}


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, attribute = _EXPORTS[name]
    module = import_module(module_name, __name__)
    value = getattr(module, attribute) if attribute else module
    globals()[name] = value
    return value


__all__ = list(_EXPORTS)
