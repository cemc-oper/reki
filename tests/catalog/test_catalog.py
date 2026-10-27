import hashlib
import subprocess
import sys

import pytest

from cedarkit_query import Catalog, QueryError, SourceError
from reki.catalog import load_catalog, load_context, load_resource


def test_configuration_import_does_not_load_readers_or_clients():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import reki.catalog; "
            "assert not any(n == 'eccodes' or n.startswith(('reki.readers', 'nuwe', 'xarray')) "
            "for n in sys.modules)",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_builtin_is_shared_model_with_no_unproven_products(monkeypatch, tmp_path):
    monkeypatch.setenv("REKI_CATALOG_PATH", str(tmp_path / "missing.yaml"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    value = load_catalog()
    assert isinstance(value, Catalog)
    assert len(value.datasets) == 18
    assert all(not dataset["products"] for dataset in value.datasets)


def test_whole_catalog_replacement_and_byte_provenance(resources):
    path = resources["context"]["catalog"]["path"]
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
    loaded = load_resource({"path": path, "version": "1", "sha256": digest}, "catalog")
    assert loaded.sha256 == digest
    assert loaded.value.datasets[0]["id"] == "synthetic"
    assert load_catalog({"path": path}) == loaded.value
    snapshot = loaded.snapshot("catalog")
    snapshot["reference"]["version"] = "999"
    assert loaded.reference["version"] == "1"


@pytest.mark.parametrize("change", [{"version": "2"}, {"sha256": "0" * 64}])
def test_bad_pin_never_falls_back(resources, change):
    with pytest.raises(QueryError) as error:
        load_catalog({**resources["context"]["catalog"], **change})
    assert error.value.code == "invalid_config"
    assert error.value.path.endswith("/" + next(iter(change)))


@pytest.mark.parametrize(
    "ref",
    [
        {"builtin": "latest"},
        {"path": "https://example.org/catalog.json"},
        {"path": "*.json"},
        {"builtin": "reki.catalog", "version": "latest"},
    ],
)
def test_invalid_resource_reference(ref):
    with pytest.raises(QueryError):
        load_catalog(ref)


def test_missing_and_directory_are_source_errors(tmp_path):
    for path, code in [
        (tmp_path / "missing.json", "resource_not_found"),
        (tmp_path, "io_error"),
    ]:
        with pytest.raises(SourceError) as error:
            load_catalog({"path": str(path)})
        assert error.value.code == code


@pytest.mark.parametrize(
    "text",
    [
        '{"api_version":"cedarkit.catalog/v1","id":"a","id":"b","version":"1","datasets":[]}',
        "api_version: cedarkit.catalog/v1\nid: a\nid: b\nversion: '1'\ndatasets: []",
    ],
)
def test_duplicate_keys_rejected(text, tmp_path):
    path = tmp_path / ("a.json" if text.startswith("{") else "a.yaml")
    path.write_text(text)
    with pytest.raises(QueryError, match="duplicate"):
        load_catalog({"path": str(path)})


def test_context_bases_and_freezing(tmp_path, monkeypatch):
    directory = tmp_path / "config"
    directory.mkdir()
    path = directory / "context.yaml"
    path.write_text("catalog:\n  path: catalog.json\n")
    from_file = load_context(path)
    monkeypatch.chdir(tmp_path)
    raw = {"catalog": {"path": "catalog.json"}}
    from_mapping = load_context(raw)
    raw["catalog"]["path"] = "changed.json"
    path.write_text("invalid: true")
    assert from_file.catalog["path"] == str(directory / "catalog.json")
    assert from_mapping.catalog["path"] == str(tmp_path / "catalog.json")
    with pytest.raises(TypeError):
        from_file.catalog["path"] = "change"


@pytest.mark.parametrize(
    "text", ["unknown: 1", "catalog: {builtin: reki.catalog, version: '2.0'}"]
)
def test_context_invalid_does_not_default(text, tmp_path):
    path = tmp_path / "context.yaml"
    path.write_text(text)
    with pytest.raises(QueryError):
        from reki.catalog import plan_source_binding

        plan_source_binding({"kind": "file", "path": "f.grb"}, context=path)
