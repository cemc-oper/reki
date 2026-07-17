from reki.core import Source


def test_name_defaults_to_none():
    assert Source.name is None


def test_kwargs_are_stored():
    src = Source(a=1, b="x")
    assert src._kwargs == {"a": 1, "b": "x"}


def test_mutate_returns_self():
    src = Source()
    assert src.mutate() is src


def test_mutate_source_returns_none():
    assert Source().mutate_source() is None
