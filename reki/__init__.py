from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("reki")
except PackageNotFoundError:
    # package is not installed
    pass

from .sources import from_source, from_source_lazily, register, Source
from .readers import ReaderCapabilities
from .core import SourceSpec, FieldQuery, FieldMetadata, FieldList, DataNotFoundError, MultipleFieldsMatchedError, UnsupportedOperationError
from .core import normalize_data_array, validate_data_array
from .catalog import load_catalog
from .cmadaas_request import CmadaasRequest, CmadaasRequestError, CmadaasNameNotMappedError, CmadaasRequestConflictError, bind_cmadaas_request
from .readers.grib.config import (
    ExternalNameResolution, ParameterAmbiguityError, ParameterConditionConflictError,
    ParameterExternalNameNotMappedError, ParameterNamespaceNotFoundError,
    ParameterNotFoundError, ParameterRecord, ParameterResolutionError,
    ResolvedParameter, resolve_external_name, resolve_parameter,
)
from . import operator

__all__ = ["from_source", "from_source_lazily", "register", "Source", "SourceSpec", "FieldQuery", "FieldMetadata", "FieldList", "ReaderCapabilities", "DataNotFoundError", "MultipleFieldsMatchedError", "UnsupportedOperationError", "normalize_data_array", "validate_data_array", "load_catalog", "CmadaasRequest", "CmadaasRequestError", "CmadaasNameNotMappedError", "CmadaasRequestConflictError", "bind_cmadaas_request", "ExternalNameResolution", "ParameterAmbiguityError", "ParameterConditionConflictError", "ParameterExternalNameNotMappedError", "ParameterNamespaceNotFoundError", "ParameterNotFoundError", "ParameterRecord", "ParameterResolutionError", "ResolvedParameter", "resolve_external_name", "resolve_parameter", "operator"]
