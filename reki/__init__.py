from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("reki")
except PackageNotFoundError:
    # package is not installed
    pass

from .sources import from_source, register, Source

__all__ = ["from_source", "register", "Source"]
