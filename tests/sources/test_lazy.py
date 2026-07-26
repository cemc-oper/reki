"""Tests for source-level laziness (LazySource / from_source_lazily)."""

import numpy as np
import pytest

import reki
from reki.core import Source
from reki.sources import REGISTERED, LazySource, SourceMaker, register


class CountingSource(Source):
    """A source recording construction and mutation in ``events``."""

    events = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        type(self).events.append("init")

    def mutate(self):
        type(self).events.append("mutate")
        return self

    def to_xarray(self, **kwargs):
        return "data"


class RemoteSource(Source):
    """A source whose mutate() would perform remote I/O."""

    remote = True

    def mutate(self):
        raise RuntimeError("remote request fired")


@pytest.fixture(autouse=True)
def restore_registry():
    saved_registered = dict(REGISTERED)
    saved_sources = dict(SourceMaker.SOURCES)
    saved_events = list(CountingSource.events)
    yield
    REGISTERED.clear()
    REGISTERED.update(saved_registered)
    SourceMaker.SOURCES.clear()
    SourceMaker.SOURCES.update(saved_sources)
    CountingSource.events = saved_events


class TestLazilyParameter:
    def test_returns_lazy_source_without_running_pipeline(self):
        register("counting", CountingSource)
        src = reki.from_source("counting", lazily=True)
        assert isinstance(src, LazySource)
        assert CountingSource.events == []

    def test_first_access_runs_pipeline_once(self):
        register("counting", CountingSource)
        src = reki.from_source("counting", lazily=True)
        assert src.to_xarray() == "data"
        assert CountingSource.events == ["init", "mutate"]
        # second access uses the cached object
        assert src.to_xarray() == "data"
        assert CountingSource.events == ["init", "mutate"]

    def test_repr_does_not_trigger_pipeline(self):
        register("counting", CountingSource)
        src = reki.from_source("counting", lazily=True)
        assert "pending" in repr(src)
        assert CountingSource.events == []
        src.to_xarray()
        assert "pending" not in repr(src)


class TestFromSourceLazily:
    def test_defers_construction(self):
        register("counting", CountingSource)
        src = reki.from_source_lazily("counting")
        assert isinstance(src, LazySource)
        assert CountingSource.events == []
        assert src.to_xarray() == "data"
        assert CountingSource.events == ["init", "mutate"]

    def test_exported_at_top_level(self):
        assert reki.from_source_lazily is not None


class TestRemoteSourcesAreLazyByDefault:
    def test_remote_source_does_not_fire_at_from_source(self):
        register("fake-remote", RemoteSource)
        src = reki.from_source("fake-remote")
        assert isinstance(src, LazySource)

    def test_remote_error_surfaces_on_access(self):
        register("fake-remote", RemoteSource)
        src = reki.from_source("fake-remote")
        with pytest.raises(RuntimeError, match="remote request fired"):
            src.to_xarray()

    def test_url_source_is_lazy_by_default(self):
        src = reki.from_source("url", "https://example.com/data.grib2")
        assert isinstance(src, LazySource)

    def test_cmadaas_source_is_lazy_by_default(self):
        src = reki.from_source("cmadaas", interface_id="x", params={})
        assert isinstance(src, LazySource)

    def test_local_sources_stay_eager(self, grib2_gfs_basic_file_path):
        from reki.readers.grib.reader import GribReader

        reader = reki.from_source("file", grib2_gfs_basic_file_path)
        assert isinstance(reader, GribReader)

        src = reki.from_source("memory", np.arange(3))
        assert not isinstance(src, LazySource)
