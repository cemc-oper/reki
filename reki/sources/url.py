"""URL source: download a remote file to disk, then read it as a local file.

Caching is deliberately minimal for now: the target file is downloaded
once and reused while it exists. A real cache (validation, eviction)
is future work (see ``doc/reki-future-development.md`` §12.2).
"""

import tempfile
from pathlib import Path
from typing import Optional, Union
from urllib.parse import urlparse

import requests
from tqdm import tqdm

from reki.core import Source
from reki.sources import get_source

#: default directory for downloaded files.
DEFAULT_DOWNLOAD_DIR = Path(tempfile.gettempdir()) / "reki" / "url"

#: chunk size of the streaming download.
CHUNK_SIZE = 1024 * 1024


def file_name_from_url(url: str) -> str:
    """Extract the file name from a URL path."""
    file_name = urlparse(url).path.rstrip("/").split("/")[-1]
    if not file_name:
        raise ValueError(f"cannot determine file name from URL: {url}")
    return file_name


def download_file(url: str, file_path: Union[str, Path]) -> Path:
    """Download ``url`` to ``file_path`` with a progress bar.

    If ``file_path`` already exists the download is skipped. The content
    is written to a temporary sibling file first and renamed on success,
    so an interrupted download is never mistaken for a complete file.
    """
    file_path = Path(file_path)
    if file_path.exists():
        return file_path

    file_path.parent.mkdir(parents=True, exist_ok=True)
    part_path = file_path.with_name(file_path.name + ".part")

    with requests.get(url, stream=True) as response:
        response.raise_for_status()
        total_size = int(response.headers.get("content-length", 0))
        with open(part_path, "wb") as f, tqdm(
                total=total_size,
                unit="B",
                unit_scale=True,
                desc=file_path.name,
        ) as progress_bar:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    f.write(chunk)
                    progress_bar.update(len(chunk))

    part_path.rename(file_path)
    return file_path


class UrlSource(Source):
    """A source for a remote file identified by a URL.

    ``mutate()`` downloads the URL to a local path and returns a
    ``FileSource`` for it, so the reader dispatch chain continues
    automatically::

        reki.from_source("url", "https://example.com/data.grib2").to_xarray()

    The download is remote I/O, so this source sets ``remote = True``:
    ``from_source()`` returns a lazy proxy and the download only
    happens on first use (e.g. ``to_xarray()``).

    Parameters
    ----------
    url
        the remote file URL.
    download_dir
        directory to download into. Defaults to a shared temp directory
        (:data:`DEFAULT_DOWNLOAD_DIR`). If the target file already
        exists the download is skipped.
    reader
        optional explicit reader forwarded to the ``FileSource``: a
        reader name (e.g. ``"grib"``) or a callable.
    **kwargs
        extra options forwarded to the reader (e.g. ``engine="cfgrib"``
        for the GRIB reader).
    """

    remote = True

    def __init__(
            self,
            url: str,
            download_dir: Optional[Union[str, Path]] = None,
            reader=None,
            **kwargs,
    ):
        super().__init__(**kwargs)
        self.url = url
        if download_dir is None:
            download_dir = DEFAULT_DOWNLOAD_DIR
        self.download_dir = Path(download_dir)
        self.reader = reader

    def local_path(self) -> Path:
        """The local path the URL is (or will be) downloaded to."""
        return self.download_dir / file_name_from_url(self.url)

    def mutate(self):
        path = download_file(self.url, self.local_path())
        kwargs = dict(self._kwargs)
        if self.reader is not None:
            kwargs["reader"] = self.reader
        return get_source("file", path, **kwargs)

    def __repr__(self):
        return f"UrlSource({self.url!r})"


source = UrlSource
