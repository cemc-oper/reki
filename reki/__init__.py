from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("reki")
except PackageNotFoundError:
    # package is not installed
    pass

from .sources import from_source, from_source_lazily, register, Source
from . import operator

__all__ = ["from_source", "from_source_lazily", "register", "Source", "operator"]
