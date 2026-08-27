from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("reki")
except PackageNotFoundError:
    # package is not installed
    pass

from .sources import from_source, from_source_lazily, register, Source
from .core import SourceSpec, FieldQuery, DataNotFoundError, MultipleFieldsMatchedError
from .core import normalize_data_array, validate_data_array
from . import operator

__all__ = ["from_source", "from_source_lazily", "register", "Source", "SourceSpec", "FieldQuery", "DataNotFoundError", "MultipleFieldsMatchedError", "normalize_data_array", "validate_data_array", "operator"]
