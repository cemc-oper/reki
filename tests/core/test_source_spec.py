from datetime import datetime, timedelta
from pathlib import Path

import pytest

from reki import SourceSpec, from_source, from_source_lazily, register
from reki.core.source import Source


class _ProbeSource(Source):
    calls = []

    def __init__(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs
        type(self).calls.append(self)


def test_source_spec_snapshots_and_redacts_nested_values():
    kwargs = {"token": "not-for-logs", "nested": {"password": "also-hidden", "values": [1]}}
    spec = SourceSpec("test_source", args=[Path("x"), timedelta(hours=1)], kwargs=kwargs)
    kwargs["nested"]["values"].append(2)
    assert spec.name == "test-source"
    assert spec.kwargs["nested"]["values"] == (1,)
    with pytest.raises(TypeError):
        spec.kwargs["other"] = 1
    assert "not-for-logs" not in repr(spec)
    assert "also-hidden" not in repr(spec)


def test_source_spec_key_is_order_independent_and_type_safe():
    first = SourceSpec("x", kwargs={"b": [1, "1", True], "a": datetime(2026, 1, 1)})
    second = SourceSpec("x", kwargs={"a": datetime(2026, 1, 1), "b": [1, "1", True]})
    assert first.normalized_key() == second.normalized_key()
    assert SourceSpec("x", kwargs={"v": 1}).normalized_key() != SourceSpec("x", kwargs={"v": "1"}).normalized_key()


@pytest.mark.parametrize("value", [{"name": "x", "unknown": 1}, {"args": []}, []])
def test_source_spec_from_dict_is_strict(value):
    with pytest.raises(TypeError):
        SourceSpec.from_dict(value)


def test_source_spec_source_entry_merges_runtime_kwargs_and_is_lazy():
    _ProbeSource.calls.clear()
    register("probe-source", _ProbeSource)
    spec = SourceSpec("probe_source", args=("fixed",), kwargs={"base": 1, "override": "spec"})
    lazy = from_source(spec, lazily=True, override="call")
    assert not _ProbeSource.calls
    assert "probe-source" in repr(lazy)
    assert lazy.args == ("fixed",)
    assert _ProbeSource.calls[0].kwargs == {"base": 1, "override": "call"}
    with pytest.raises(TypeError, match="positional"):
        from_source(spec, "ambiguous")


def test_source_spec_lazy_helper_accepts_spec():
    _ProbeSource.calls.clear()
    register("probe-source", _ProbeSource)
    lazy = from_source_lazily(SourceSpec("probe-source", kwargs={"secret": "hidden"}))
    assert "hidden" not in repr(lazy)
    assert not _ProbeSource.calls
    assert isinstance(lazy.kwargs, dict)
