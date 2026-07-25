"""Tests for the GRIB reader dispatch (query API is tested separately)."""

import reki.readers
from reki.core import Source
from reki.readers import reader
from reki.readers.grib.reader import GribReader


class FakeSource(Source):
    pass


def test_grib_magic_claims_grib_file(grib2_gfs_basic_file_path):
    r = reader(FakeSource(), grib2_gfs_basic_file_path)
    assert isinstance(r, GribReader)
    assert r.path == str(grib2_gfs_basic_file_path)


def test_grib_magic_rejects_other_files(tmp_path):
    path = tmp_path / "data.bin"
    path.write_bytes(b"\x89HDF\r\n\x1a\n" + b"\x00" * 64)
    assert reki.readers.grib.READER(FakeSource(), path, magic=b"\x89HDF\r\n\x1a\n") is None
