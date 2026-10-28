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
    "CmadaasRequest": (".cmadaas_request", "CmadaasRequest"),
    "CmadaasRequestError": (".cmadaas_request", "CmadaasRequestError"),
    "CmadaasNameNotMappedError": (".cmadaas_request", "CmadaasNameNotMappedError"),
    "CmadaasRequestConflictError": (".cmadaas_request", "CmadaasRequestConflictError"),
    "bind_cmadaas_request": (".cmadaas_request", "bind_cmadaas_request"),
    "ExternalNameResolution": (".readers.grib.config", "ExternalNameResolution"),
    "ParameterAmbiguityError": (".readers.grib.config", "ParameterAmbiguityError"),
    "ParameterConditionConflictError": (
        ".readers.grib.config",
        "ParameterConditionConflictError",
    ),
    "ParameterExternalNameNotMappedError": (
        ".readers.grib.config",
        "ParameterExternalNameNotMappedError",
    ),
    "ParameterNamespaceNotFoundError": (
        ".readers.grib.config",
        "ParameterNamespaceNotFoundError",
    ),
    "ParameterNotFoundError": (".readers.grib.config", "ParameterNotFoundError"),
    "ParameterRecord": (".readers.grib.config", "ParameterRecord"),
    "ParameterResolutionError": (".readers.grib.config", "ParameterResolutionError"),
    "ResolvedParameter": (".readers.grib.config", "ResolvedParameter"),
    "resolve_external_name": (".readers.grib.config", "resolve_external_name"),
    "resolve_parameter": (".readers.grib.config", "resolve_parameter"),
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
