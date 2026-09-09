"""Local file source."""

import os

from reki.core import Source


class FileSource(Source):
    """A source for a local data file, format auto-detected by readers.

    Parameters
    ----------
    path
        path of the data file.
    reader
        optional explicit reader: a reader name (e.g. ``"grib"``) or a
        callable. When given, the reader auto-detection is skipped.
    **kwargs
        extra options forwarded to the reader (e.g. ``engine="cfgrib"``
        for the GRIB reader).
    """

    def __init__(self, path, reader=None, **kwargs):
        super().__init__(**kwargs)
        self.path = os.path.expanduser(str(path))
        self.reader = reader

    def mutate(self):
        return self

    def to_data_object(self):
        from reki.readers import reader

        return reader(self, self.path, **self._kwargs)

    def __fspath__(self):
        return self.path

    def __repr__(self):
        return f"FileSource({self.path!r})"


source = FileSource
