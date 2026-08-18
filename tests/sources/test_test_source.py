"""Tests for the built-in reki ``test`` source (``reki.sources.test``).

The download itself is faked (``download_gfs_data`` is monkeypatched);
these tests cover the source's mutate chain and its discovery through
the built-in directory scan.
"""

from pathlib import Path

import pandas as pd
import pytest

import reki
import reki.sources.test
from reki.sources import get_source
from reki.sources.file import FileSource
from reki.sources.test import DEFAULT_DATA_DIR, TestSource


@pytest.fixture
def fake_download(monkeypatch, tmp_path):
    """Replace download_gfs_data with a recorder returning a GRIB file.

    The file only carries the GRIB magic bytes: that is enough for the
    reki reader dispatch to claim it (no message is decoded).
    """
    grib_file = tmp_path / "fake.grib2"
    grib_file.write_bytes(b"GRIB" + b"\x00" * 12)
    calls = []

    def fake_download_gfs_data(**kwargs):
        calls.append(kwargs)
        return grib_file

    monkeypatch.setattr(
        reki.sources.test,
        "download_gfs_data",
        fake_download_gfs_data,
    )
    return calls


@pytest.fixture
def fake_ifs_download(monkeypatch, tmp_path):
    """Replace download_ecmwf_ifs_data with a recorder (see fake_download)."""
    grib_file = tmp_path / "fake_ifs.grib2"
    grib_file.write_bytes(b"GRIB" + b"\x00" * 12)
    calls = []

    def fake_download_ecmwf_ifs_data(**kwargs):
        calls.append(kwargs)
        return grib_file

    monkeypatch.setattr(
        reki.sources.test,
        "download_ecmwf_ifs_data",
        fake_download_ecmwf_ifs_data,
    )
    return calls


class TestValidation:
    def test_unknown_dataset_name(self):
        with pytest.raises(ValueError, match="unknown test dataset"):
            TestSource("no-such-dataset")

    def test_default_output_dir(self):
        source = TestSource("gfs")
        assert source.output_dir == DEFAULT_DATA_DIR

    def test_gfs_alias_normalizes_to_cma_gfs(self):
        source = TestSource("gfs")
        assert source.dataset_name == "cma_gfs"

    def test_unknown_ifs_domain(self):
        with pytest.raises(ValueError, match="unknown ecmwf_ifs domain"):
            reki.sources.test.download_ecmwf_ifs_data(
                output_dir=Path("/nonexistent"), domain="mars",
            )


class TestMutate:
    def test_mutate_returns_file_source(self, fake_download, tmp_path):
        source = TestSource("gfs", output_dir=tmp_path)

        mutated = source.mutate()

        assert isinstance(mutated, FileSource)
        assert mutated.path == str(tmp_path / "fake.grib2")

    def test_arguments_forwarded(self, fake_download, tmp_path):
        start_time = pd.Timestamp("2026-07-25T00:00")
        forecast_time = pd.Timedelta(hours=12)
        source = TestSource(
            "gfs",
            output_dir=tmp_path,
            source="music-dir",
            storage_base="/mnt/music",
            start_time=start_time,
            forecast_time=forecast_time,
        )

        source.mutate()

        assert fake_download == [{
            "output_dir": tmp_path,
            "source": "music-dir",
            "storage_base": "/mnt/music",
            "start_time": start_time,
            "forecast_time": forecast_time,
        }]

    def test_mutate_ecmwf_ifs(self, fake_ifs_download, tmp_path):
        source = TestSource("ecmwf_ifs", output_dir=tmp_path, domain="global")

        mutated = source.mutate()

        assert isinstance(mutated, FileSource)
        assert mutated.path == str(tmp_path / "fake_ifs.grib2")
        assert fake_ifs_download == [{
            "output_dir": tmp_path,
            "domain": "global",
        }]

    def test_gfs_alias_dispatches_to_gfs_backend(self, fake_download, tmp_path):
        source = TestSource("gfs", output_dir=tmp_path)

        mutated = source.mutate()

        assert isinstance(mutated, FileSource)
        assert len(fake_download) == 1


class TestDiscovery:
    def test_discovered_by_name(self):
        source = get_source("test", "gfs")
        assert isinstance(source, TestSource)
        assert source.name == "test"

    def test_end_to_end(self, fake_download, tmp_path):
        """from_source("test", ...) mutates into a file reader.

        TestSource is marked ``remote = True``, so ``from_source``
        returns a lazy proxy; force the pipeline by touching it.
        """
        from reki.readers.grib.reader import GribReader
        from reki.sources import LazySource

        data = reki.from_source("test", "gfs", output_dir=tmp_path)

        assert isinstance(data, LazySource)
        assert isinstance(data._ensure(), GribReader)

    def test_end_to_end_ecmwf_ifs(self, fake_ifs_download, tmp_path):
        from reki.readers.grib.reader import GribReader
        from reki.sources import LazySource

        data = reki.from_source("test", "ecmwf_ifs", output_dir=tmp_path)

        assert isinstance(data, LazySource)
        assert isinstance(data._ensure(), GribReader)
