"""Dataset catalog loading and source specification resolution.

The catalog is deliberately a pure configuration layer: resolving a dataset
never imports a reader, scans a path, or opens a network connection.
"""

from .model import Catalog, DatasetRecord, ResolvedDataset
from .loader import CatalogError, load_catalog

__all__ = ["Catalog", "CatalogError", "DatasetRecord", "ResolvedDataset", "load_catalog"]
