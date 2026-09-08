"""Tests for the built-in reki ``test`` source (``reki.sources.test``).

The download itself is faked (``download_gfs_data`` is monkeypatched);
these tests cover the source's mutate chain and its discovery through
the built-in directory scan.
"""

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
import requests
import yaml
from click.testing import CliRunner

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
            "variant": None,
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


class TestEcmwfIfsDownload:
    asset_bytes = b"verified IFS asset"

    @staticmethod
    def _manifest():
        return {
            "dataset_version": reki.sources.test.ECMWF_IFS_RELEASE_TAG,
            "assets": {
                name: {
                    "file": f"ifs_{name}.grib2",
                    "sha256": hashlib.sha256(TestEcmwfIfsDownload.asset_bytes).hexdigest(),
                }
                for name in reki.sources.test.ECMWF_IFS_VARIANTS
            },
        }

    @pytest.fixture
    def fake_release(self, monkeypatch):
        manifest_calls = []
        download_calls = []
        manifest_bytes = json.dumps(self._manifest()).encode()

        class Response:
            content = manifest_bytes

            def raise_for_status(self):
                pass

        def fake_get(url, **kwargs):
            manifest_calls.append((url, kwargs))
            return Response()

        def fake_download(url, path):
            download_calls.append((url, path))
            Path(path).write_bytes(self.asset_bytes)
            return Path(path)

        monkeypatch.setattr(reki.sources.test.requests, "get", fake_get)
        monkeypatch.setattr(reki.sources.test, "download_file", fake_download)
        monkeypatch.setattr(
            reki.sources.test,
            "ECMWF_IFS_MANIFEST_SHA256",
            hashlib.sha256(manifest_bytes).hexdigest(),
        )
        return manifest_calls, download_calls

    def test_downloads_manifest_asset_and_metadata(self, fake_release, tmp_path):
        manifest_calls, download_calls = fake_release

        path = reki.sources.test.download_ecmwf_ifs_data(
            tmp_path, variant="layers",
        )

        assert path == tmp_path / "ifs_layers.grib2"
        assert len(manifest_calls) == 1
        assert len(download_calls) == 1
        metadata = yaml.safe_load((tmp_path / "metadata.yaml").read_text())[0]
        assert metadata["variant"] == "layers"
        assert metadata["release_tag"] == reki.sources.test.ECMWF_IFS_RELEASE_TAG
        assert metadata["checksum"]["algorithm"] == "sha256"

    def test_cache_hit_is_offline_and_checksum_verified(self, fake_release, tmp_path):
        manifest_calls, download_calls = fake_release

        first = reki.sources.test.download_ecmwf_ifs_data(tmp_path)
        second = reki.sources.test.download_ecmwf_ifs_data(tmp_path)

        assert first == second
        assert len(manifest_calls) == 1
        assert len(download_calls) == 1

    def test_default_and_legacy_global_selectors_remain_compatible(
        self, fake_release, tmp_path,
    ):
        core = reki.sources.test.download_ecmwf_ifs_data(tmp_path)
        global_ = reki.sources.test.download_ecmwf_ifs_data(
            tmp_path, domain="global",
        )

        assert core.name == "ifs_core.grib2"
        assert global_.name == "ifs_global.grib2"

    def test_corrupt_cache_is_redownloaded(self, fake_release, tmp_path):
        _, download_calls = fake_release
        path = reki.sources.test.download_ecmwf_ifs_data(tmp_path)
        path.write_bytes(b"corrupt")

        reki.sources.test.download_ecmwf_ifs_data(tmp_path)

        assert len(download_calls) == 2
        assert path.read_bytes() == self.asset_bytes

    def test_bad_download_is_removed_before_it_can_be_read(
        self, fake_release, monkeypatch, tmp_path,
    ):
        def corrupt_download(url, path):
            Path(path).write_bytes(b"bad download")
            return Path(path)

        monkeypatch.setattr(reki.sources.test, "download_file", corrupt_download)
        with pytest.raises(ValueError, match="checksum mismatch"):
            reki.sources.test.download_ecmwf_ifs_data(tmp_path, variant="time")

        assert not (tmp_path / "ifs_time.grib2").exists()

    def test_unknown_variant_does_not_request_network(self, fake_release, tmp_path):
        manifest_calls, _ = fake_release

        with pytest.raises(ValueError, match="unknown ecmwf_ifs variant"):
            reki.sources.test.download_ecmwf_ifs_data(tmp_path, variant="mars")

        assert manifest_calls == []

    def test_conflicting_domain_and_variant_is_rejected(self, fake_release, tmp_path):
        with pytest.raises(ValueError, match="conflicts"):
            reki.sources.test.download_ecmwf_ifs_data(
                tmp_path, domain="global", variant="time",
            )

    def test_manifest_network_failure_is_reported(self, monkeypatch, tmp_path):
        def fail(*args, **kwargs):
            raise requests.ConnectionError("offline")

        monkeypatch.setattr(reki.sources.test.requests, "get", fail)
        with pytest.raises(requests.ConnectionError, match="offline"):
            reki.sources.test.download_ecmwf_ifs_data(tmp_path)

    def test_cli_forwards_variant(self, monkeypatch, tmp_path):
        calls = []

        def fake_download(**kwargs):
            calls.append(kwargs)
            path = kwargs["output_dir"] / "fake.grib2"
            path.write_bytes(b"GRIB" + b"\\0" * 12)
            return path

        monkeypatch.setattr(reki.sources.test, "download_ecmwf_ifs_data", fake_download)
        result = CliRunner().invoke(
            reki.sources.test.main,
            ["download", "ecmwf_ifs", "--variant", "ensemble", "--output", str(tmp_path)],
        )

        assert result.exit_code == 0, result.output
        assert "Variant: ensemble" in result.output
        assert calls == [{"output_dir": tmp_path, "domain": None, "variant": "ensemble"}]
