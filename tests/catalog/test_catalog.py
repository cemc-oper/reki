import pytest

from reki.catalog import CatalogError, load_catalog


def document(*datasets):
    return {"api_version": "reki.catalog/v1", "datasets": list(datasets)}


def dataset(dataset_id="demo", aliases=(), **kwargs):
    return {"id": dataset_id, "aliases": list(aliases), "source": {
        "name": "memory", "kwargs": kwargs,
    }}


def test_resolve_is_pure_and_tracks_origin():
    catalog = load_catalog(builtin=False, plugins=False, user=False, explicit=document(dataset("demo", ["legacy"], token="secret")))
    resolved = catalog.resolve("legacy")
    assert resolved.record.dataset_id == "demo"
    assert resolved.source.kwargs["token"] == "secret"
    assert resolved.origin == "explicit"


def test_replacement_is_whole_record_and_diagnostic_is_preserved():
    catalog = load_catalog(builtin=False, plugins=False, user=False, explicit=document(dataset("demo", ["new"])))
    assert catalog.resolve("demo").record.aliases == ("new",)


def test_unknown_fields_and_alias_conflicts_fail():
    with pytest.raises(CatalogError, match="unknown catalog fields"):
        load_catalog(builtin=False, plugins=False, user=False, explicit={"api_version": "reki.catalog/v1", "datasets": [], "extra": True})
    with pytest.raises(CatalogError, match="duplicate dataset alias"):
        load_catalog(builtin=False, plugins=False, user=False, explicit=document(dataset("one", ["same"]), dataset("two", ["same"])))
