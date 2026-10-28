"""Terminal file utilities exercised only on disposable SYNTHETIC files."""

from dataclasses import replace
from types import SimpleNamespace
import pytest

from cedarkit_query import QueryError, SourceError
from reki.catalog.model import freeze
from reki.selection.files import discover_paths, FileSnapshot


def test_literal_file_order_and_directory_glob_sorting(factory, tmp_path):
    a, b = tmp_path / "b[1].grib2", tmp_path / "a.grib2"
    a.write_bytes(b"SYNTHETIC")
    b.write_bytes(b"SYNTHETIC")
    source, _, _ = factory()
    config = replace(
        source.configuration,
        source=freeze(dict(kind="file", path=[str(a), str(b), str(a)])),
    )
    assert discover_paths(config) == (a, b)
    config = replace(
        config,
        source=freeze(
            dict(kind="file", directory=str(tmp_path), glob=["*.grib2", "a*"])
        ),
    )
    assert discover_paths(config) == (b, a)
    config = replace(
        config, source=freeze(dict(kind="file", directory=str(tmp_path), glob="../*"))
    )
    with pytest.raises(QueryError):
        discover_paths(config)


def test_registered_local_layout_pairing_and_no_rounding(tmp_path, q):
    # A locator unit test; no real product or deployment layout is activated.
    config = SimpleNamespace(
        source={"kind": "local", "root": str(tmp_path)},
        layout=(
            "{year}/{date_label}/SYNTHETIC_{start_time_label}_{forecast_hour_label}_{member_3digit}",
        ),
        execution_defaults={"max_expansion": 10},
        member_roles={},
        cemc_member_roles=False,
    )
    a = {**q.to_dict(), "member": 2}
    b = {**q.to_dict(), "step": "PT12H", "member": 0}
    b.pop("valid_time")
    assert discover_paths(config, [a, b]) == (
        tmp_path / "2026/20260101/SYNTHETIC_2026010100_006_002",
        tmp_path / "2026/20260101/SYNTHETIC_2026010100_012_000",
    )
    for changes in ({"step": "PT30M"}, {"time": "2026-01-01T00:00:00.1Z"}):
        invalid = {**a, **changes}
        invalid.pop("valid_time", None)
        with pytest.raises(QueryError):
            discover_paths(config, [invalid])


def test_local_template_symlink_cannot_escape_root(tmp_path, q):
    root = tmp_path / "root"
    root.mkdir()
    (root / "outside").symlink_to(tmp_path, target_is_directory=True)
    config = SimpleNamespace(
        source={"kind": "local", "root": str(root)},
        layout=("outside/file",),
        execution_defaults={"max_expansion": 10},
        member_roles={},
        cemc_member_roles=False,
    )
    with pytest.raises(QueryError):
        discover_paths(config, [q])


def test_file_snapshot_replacement_and_mutation_during_load(tmp_path):
    path = tmp_path / "SYNTHETIC"
    path.write_bytes(b"first")
    snapshot = FileSnapshot.capture(path)
    assert snapshot.load(lambda: b"value") == b"value"
    replacement = tmp_path / "replacement"
    replacement.write_bytes(b"first")
    replacement.replace(path)
    with pytest.raises(SourceError) as exc:
        snapshot.load(lambda: b"must not load")
    assert exc.value.context["reason"] == "resource_changed"
    snapshot = FileSnapshot.capture(path)

    def race():
        path.write_bytes(b"modified during value load")

    with pytest.raises(SourceError):
        snapshot.load(race)
