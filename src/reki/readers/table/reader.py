"""Table reader bound to the ``reader()`` dispatch.

Tables are plain text files with no reliable magic bytes, so this
reader only claims files in the deeper probing pass, by extension.
"""

import os

import pandas as pd

from reki.readers import Reader

from . import load_table_from_file

#: file extensions claimed by the table reader (deeper pass only).
TABLE_EXTENSIONS = (".txt", ".csv", ".tsv", ".tab")


class TableReader(Reader):
    """Reader for plain text tables, wrapping ``pandas.DataFrame``."""

    def __init__(self, source, path, sep=r"\s+|,", **kwargs):
        super().__init__(source, path)
        self._sep = sep

    def to_pandas(self, **kwargs) -> pd.DataFrame:
        kwargs.setdefault("sep", self._sep)
        return load_table_from_file(self.path, **kwargs)

    def to_xarray(self, **kwargs):
        return self.to_pandas(**kwargs).to_xarray()

    def to_numpy(self, **kwargs):
        return self.to_pandas(**kwargs).to_numpy()


def READER(source, path, magic=None, deeper_check=False, **kwargs):
    """Claim text table files by extension, in the deeper pass only."""
    if not deeper_check:
        return None
    if os.path.splitext(str(path))[1].lower() in TABLE_EXTENSIONS:
        return TableReader(source, path, **kwargs)
    return None
