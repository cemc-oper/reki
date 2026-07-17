import numpy as np
import pytest

import reki
from reki.core import Source
from reki.sources import REGISTERED, SourceMaker, register


class MutatingSource(Source):
    """A source that mutates into a new instance until steps reach 0."""

    def __init__(self, steps: int = 0, **kwargs):
        super().__init__(**kwargs)
        self.steps = steps

    def mutate(self):
        if self.steps <= 0:
            return self
        return MutatingSource(steps=self.steps - 1)


@pytest.fixture(autouse=True)
def restore_registry():
    saved_registered = dict(REGISTERED)
    saved_sources = dict(SourceMaker.SOURCES)
    yield
    REGISTERED.clear()
    REGISTERED.update(saved_registered)
    SourceMaker.SOURCES.clear()
    SourceMaker.SOURCES.update(saved_sources)


def test_from_source_runs_mutate_until_fixed_point():
    register("mutating", MutatingSource)
    src = reki.from_source("mutating", steps=3)
    assert isinstance(src, MutatingSource)
    assert src.steps == 0


def test_from_source_returns_converged_source():
    src = reki.from_source("memory", np.arange(3))
    assert src.mutate() is src


def test_from_source_is_exported_at_top_level():
    assert reki.from_source is not None
    assert reki.register is not None
    assert reki.Source is Source


def test_from_source_unknown_name():
    with pytest.raises(ValueError, match="Unknown source"):
        reki.from_source("no-such-source")


def test_from_source_lazily_not_implemented():
    with pytest.raises(NotImplementedError):
        reki.from_source("memory", np.arange(3), lazily=True)
