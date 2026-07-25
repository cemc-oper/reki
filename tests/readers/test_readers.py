import pytest

import reki.readers
from reki.core import Source
from reki.readers import Reader, UnknownReader, reader


class FakeSource(Source):
    pass


@pytest.fixture
def data_file(tmp_path):
    path = tmp_path / "data.bin"
    path.write_bytes(b"GRIB" + b"\x00" * 100)
    return path


@pytest.fixture
def patch_readers(monkeypatch):
    """Replace the factory registry with a controllable dict."""
    factories = {}
    monkeypatch.setattr(reki.readers, "_readers", lambda method="reader": factories)
    return factories


class TestReaderBase:
    def test_stores_source_and_path(self, data_file):
        source = FakeSource()
        r = Reader(source, data_file)
        assert r.source is source
        assert r.path == str(data_file)

    def test_mutate_returns_self(self, data_file):
        r = Reader(FakeSource(), data_file)
        assert r.mutate() is r

    def test_mutate_source_returns_none(self, data_file):
        assert Reader(FakeSource(), data_file).mutate_source() is None

    @pytest.mark.parametrize("method", ["to_xarray", "to_pandas", "to_numpy"])
    def test_conversions_raise_not_implemented(self, data_file, method):
        with pytest.raises(NotImplementedError):
            getattr(Reader(FakeSource(), data_file), method)()


class TestDispatch:
    def test_first_hit_wins(self, data_file, patch_readers):
        calls = []

        def factory_a(source, path, magic=None, deeper_check=False, **kwargs):
            calls.append(("a", deeper_check))
            return Reader(source, path)

        def factory_b(source, path, magic=None, deeper_check=False, **kwargs):
            calls.append(("b", deeper_check))
            return Reader(source, path)

        patch_readers["a"] = factory_a
        patch_readers["b"] = factory_b

        r = reader(FakeSource(), data_file)
        assert isinstance(r, Reader)
        assert calls == [("a", False)]

    def test_two_pass_probing(self, data_file, patch_readers):
        calls = []

        def quick_only(source, path, magic=None, deeper_check=False, **kwargs):
            calls.append(("quick", deeper_check))
            return None

        def deep_only(source, path, magic=None, deeper_check=False, **kwargs):
            calls.append(("deep", deeper_check))
            return Reader(source, path) if deeper_check else None

        patch_readers["quick"] = quick_only
        patch_readers["deep"] = deep_only

        r = reader(FakeSource(), data_file)
        assert isinstance(r, Reader)
        assert calls == [
            ("quick", False), ("deep", False),
            ("quick", True), ("deep", True),
        ]

    def test_magic_bytes_are_passed(self, data_file, patch_readers):
        seen = {}

        def factory(source, path, magic=None, deeper_check=False, **kwargs):
            seen["magic"] = magic
            return None

        patch_readers["fake"] = factory
        reader(FakeSource(), data_file)
        assert seen["magic"] is not None
        assert seen["magic"].startswith(b"GRIB")

    def test_reader_mutate_is_called(self, data_file, patch_readers):
        class MutatingReader(Reader):
            def mutate(self):
                return "mutated"

        patch_readers["fake"] = lambda source, path, **kw: MutatingReader(source, path)
        assert reader(FakeSource(), data_file) == "mutated"

    def test_missing_file_raises(self, tmp_path, patch_readers):
        with pytest.raises(FileNotFoundError):
            reader(FakeSource(), tmp_path / "missing.grib")

    def test_fallback_to_unknown_reader(self, data_file, patch_readers):
        patch_readers["fake"] = lambda source, path, **kw: None
        r = reader(FakeSource(), data_file)
        assert isinstance(r, UnknownReader)
        assert r.to_bytes().startswith(b"GRIB")


class TestExplicitReader:
    def test_explicit_reader_name(self, data_file, patch_readers):
        seen = {}

        def factory(source, path, magic=None, deeper_check=False, **kwargs):
            seen["magic"] = magic
            seen["deeper_check"] = deeper_check
            return Reader(source, path)

        patch_readers["my_reader"] = factory

        source = FakeSource()
        source.reader = "my-reader"
        r = reader(source, data_file)
        assert isinstance(r, Reader)
        assert seen == {"magic": None, "deeper_check": False}

    def test_explicit_unknown_reader_name(self, data_file, patch_readers):
        source = FakeSource()
        source.reader = "no-such-reader"
        with pytest.raises(ValueError, match="Unknown reader"):
            reader(source, data_file)

    def test_explicit_callable(self, data_file, patch_readers):
        source = FakeSource()
        source.reader = lambda src, path: Reader(src, path)
        assert isinstance(reader(source, data_file), Reader)

    def test_explicit_invalid_type(self, data_file, patch_readers):
        source = FakeSource()
        source.reader = 42
        with pytest.raises(TypeError, match="callable or a string"):
            reader(source, data_file)

    def test_explicit_reader_skips_existence_check(self, tmp_path, patch_readers):
        source = FakeSource()
        source.reader = lambda src, path: Reader(src, path)
        r = reader(source, tmp_path / "missing.grib")
        assert isinstance(r, Reader)


class TestDirectoryScan:
    def test_scan_returns_dict(self):
        assert isinstance(reki.readers._readers(), dict)
