"""Tests for the URL source (download to disk, then read as a local file).

All HTTP access is mocked; no real network is needed.
"""

import pytest
import requests
import xarray as xr

import reki
import reki.sources.url
from reki.sources.file import FileSource
from reki.sources.url import UrlSource, download_file, file_name_from_url
from reki.readers.grib import GribReader


MOCK_URL = "https://example.com/data/Z_TEST_02400.grib2"


class FakeResponse:
    """A minimal stand-in for a streaming ``requests`` response."""

    def __init__(self, content: bytes = b"", status_code: int = 200):
        self._content = content
        self.status_code = status_code
        self.headers = {"content-length": str(len(content))}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error for url")

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self._content), chunk_size):
            yield self._content[i:i + chunk_size]


@pytest.fixture
def mock_get(monkeypatch):
    """Replace ``requests.get`` with a recorder returning a FakeResponse."""
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return fake_get.response

    fake_get.response = FakeResponse()
    fake_get.calls = calls
    monkeypatch.setattr(reki.sources.url.requests, "get", fake_get)
    return fake_get


@pytest.fixture(autouse=True)
def quiet_tqdm(monkeypatch):
    """Silence the progress bar during tests."""
    class FakeTqdm:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def update(self, n):
            pass

    monkeypatch.setattr(reki.sources.url, "tqdm", FakeTqdm)


@pytest.fixture
def grib_message_bytes(grib2_gfs_basic_file_path):
    """The first GRIB message (acpcp at surface) of the GFS test file."""
    with open(grib2_gfs_basic_file_path, "rb") as f:
        header = f.read(16)
        assert header[:4] == b"GRIB" and header[7] == 2
        length = int.from_bytes(header[8:16], "big")
        f.seek(0)
        return f.read(length)


class TestFileNameFromUrl:
    def test_simple_url(self):
        assert file_name_from_url(MOCK_URL) == "Z_TEST_02400.grib2"

    def test_trailing_slash(self):
        assert file_name_from_url(MOCK_URL + "/") == "Z_TEST_02400.grib2"

    def test_nameless_url_raises(self):
        with pytest.raises(ValueError, match="file name"):
            file_name_from_url("https://example.com/")


class TestDownloadFile:
    def test_download_writes_content(self, mock_get, tmp_path):
        mock_get.response = FakeResponse(b"fake-grib-bytes")
        file_path = tmp_path / "sub" / "data.bin"

        result = download_file(MOCK_URL, file_path)

        assert result == file_path
        assert file_path.read_bytes() == b"fake-grib-bytes"
        assert mock_get.calls[0][0] == MOCK_URL
        assert mock_get.calls[0][1].get("stream") is True

    def test_existing_file_skips_download(self, mock_get, tmp_path):
        file_path = tmp_path / "data.bin"
        file_path.write_bytes(b"already here")

        result = download_file(MOCK_URL, file_path)

        assert result == file_path
        assert file_path.read_bytes() == b"already here"
        assert mock_get.calls == []

    def test_http_error_raises_and_leaves_no_file(self, mock_get, tmp_path):
        mock_get.response = FakeResponse(status_code=404)
        file_path = tmp_path / "data.bin"

        with pytest.raises(requests.HTTPError):
            download_file(MOCK_URL, file_path)

        assert not file_path.exists()
        assert not file_path.with_name("data.bin.part").exists()

    def test_interrupted_download_is_retried(self, mock_get, tmp_path):
        class BrokenResponse(FakeResponse):
            def iter_content(self, chunk_size=1):
                yield b"partial"
                raise ConnectionError("connection reset")

        mock_get.response = BrokenResponse(b"ignored")
        file_path = tmp_path / "data.bin"

        with pytest.raises(ConnectionError):
            download_file(MOCK_URL, file_path)
        assert not file_path.exists()

        mock_get.response = FakeResponse(b"full content")
        download_file(MOCK_URL, file_path)
        assert file_path.read_bytes() == b"full content"


class TestUrlSource:
    def test_local_path_uses_url_file_name(self, tmp_path):
        src = UrlSource(MOCK_URL, download_dir=tmp_path)
        assert src.local_path() == tmp_path / "Z_TEST_02400.grib2"

    def test_default_download_dir(self):
        src = UrlSource(MOCK_URL)
        assert src.local_path().parent == reki.sources.url.DEFAULT_DOWNLOAD_DIR

    def test_mutate_downloads_and_returns_file_source(self, mock_get, tmp_path):
        mock_get.response = FakeResponse(b"fake-grib-bytes")
        src = UrlSource(MOCK_URL, download_dir=tmp_path)

        file_src = src.mutate()

        assert isinstance(file_src, FileSource)
        assert file_src.path == str(tmp_path / "Z_TEST_02400.grib2")
        assert (tmp_path / "Z_TEST_02400.grib2").read_bytes() == b"fake-grib-bytes"

    def test_mutate_forwards_reader_and_kwargs(self, mock_get, tmp_path):
        mock_get.response = FakeResponse(b"fake-grib-bytes")
        src = UrlSource(
            MOCK_URL, download_dir=tmp_path, reader="grib", engine="cfgrib",
        )

        file_src = src.mutate()

        assert file_src.reader == "grib"
        assert file_src._kwargs["engine"] == "cfgrib"


class TestFromSourceUrl:
    def test_end_to_end_grib(self, mock_get, tmp_path, grib_message_bytes):
        mock_get.response = FakeResponse(grib_message_bytes)

        data = reki.from_source(
            "url", MOCK_URL, download_dir=tmp_path,
        ).to_xarray()

        assert isinstance(data, xr.DataArray)
        # the first message of the GFS test file is acpcp at surface,
        # decoded under its CEMC parameter table name
        assert data.name == "rainc"
        assert data.attrs["eccodes_name"] == "acpcp"

    def test_explicit_reader_skips_detection(
            self, mock_get, tmp_path, grib_message_bytes
    ):
        mock_get.response = FakeResponse(grib_message_bytes)

        # the url source is remote, so from_source() defers the
        # download and reader dispatch to first use
        reader = reki.from_source(
            "url", MOCK_URL, download_dir=tmp_path, reader="grib",
        )._ensure()

        assert isinstance(reader, GribReader)
