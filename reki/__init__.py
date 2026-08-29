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
from .readers.grib.config import (
    ParameterAmbiguityError, ParameterConditionConflictError,
    ParameterNotFoundError, ParameterRecord, ParameterResolutionError,
    ResolvedParameter, resolve_parameter,
)
from . import operator

__all__ = ["from_source", "from_source_lazily", "register", "Source", "SourceSpec", "FieldQuery", "FieldMetadata", "FieldList", "ReaderCapabilities", "DataNotFoundError", "MultipleFieldsMatchedError", "UnsupportedOperationError", "normalize_data_array", "validate_data_array", "load_catalog", "ParameterAmbiguityError", "ParameterConditionConflictError", "ParameterNotFoundError", "ParameterRecord", "ParameterResolutionError", "ResolvedParameter", "resolve_parameter", "operator"]
