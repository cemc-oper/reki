import pytest

import reki.sources
from reki.core import Source
from reki.sources import REGISTERED, SourceMaker, get_source, register


class FakeSource(Source):
    pass


class OtherSource(Source):
    pass


@pytest.fixture(autouse=True)
def restore_registry():
    """Snapshot and restore global source registries around each test."""
    saved_registered = dict(REGISTERED)
    saved_sources = dict(SourceMaker.SOURCES)
    yield
    REGISTERED.clear()
    REGISTERED.update(saved_registered)
    SourceMaker.SOURCES.clear()
    SourceMaker.SOURCES.update(saved_sources)


def test_programmatic_register():
    register("fake", FakeSource)
    src = get_source("fake")
    assert isinstance(src, FakeSource)


def test_programmatic_register_wins_over_builtin():
    SourceMaker.SOURCES.pop("memory", None)
    register("memory", FakeSource)
    src = get_source("memory")
    assert isinstance(src, FakeSource)


def test_name_normalization_underscore_and_hyphen():
    register("my_source", FakeSource)
    assert isinstance(get_source("my-source"), FakeSource)

    register("my-other-source", OtherSource)
    assert isinstance(get_source("my_other_source"), OtherSource)


def test_directory_scan_finds_builtin_memory():
    import numpy as np

    src = get_source("memory", np.arange(3))
    assert type(src).__name__ == "MemorySource"
    assert src.name == "memory"


def test_name_is_set_on_source():
    register("fake", FakeSource)
    assert get_source("fake").name == "fake"


def test_unknown_source_raises_value_error():
    with pytest.raises(ValueError, match="Unknown source"):
        get_source("no-such-source")


def test_result_is_cached():
    register("fake", FakeSource)
    get_source("fake")
    assert SourceMaker.SOURCES["fake"] is FakeSource


def test_getattr_lookup():
    register("fake", FakeSource)
    assert isinstance(get_source.fake, FakeSource)


def test_entry_point_source(monkeypatch):
    class FakeEntryPoint:
        name = "ep-source"

        def load(self):
            return FakeSource

    monkeypatch.setattr(
        reki.sources, "entry_points", lambda group=None: [FakeEntryPoint()]
    )
    assert isinstance(get_source("ep_source"), FakeSource)


def test_entry_point_source_module_form(monkeypatch):
    import types

    module = types.SimpleNamespace(source=FakeSource)

    class FakeEntryPoint:
        name = "ep-module-source"

        def load(self):
            return module

    monkeypatch.setattr(
        reki.sources, "entry_points", lambda group=None: [FakeEntryPoint()]
    )
    assert isinstance(get_source("ep-module-source"), FakeSource)
