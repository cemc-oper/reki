from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("reki")
except PackageNotFoundError:
    # package is not installed
    pass
