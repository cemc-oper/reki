"""Terminal file utilities exercised only on disposable SYNTHETIC files."""

from dataclasses import replace
from types import SimpleNamespace
import pytest

from cedarkit_query import QueryError, SourceError
from reki.catalog import plan_source_binding
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
    # Without a lead, discover existing files for this exact origin/member only.
    selected = tmp_path / "2026/20260101/SYNTHETIC_2026010100_012_002"
    selected.parent.mkdir(parents=True)
    selected.write_bytes(b"SYNTHETIC")
    (selected.parent / "SYNTHETIC_2026010100_012_000").write_bytes(b"OTHER MEMBER")
    (selected.parent / "SYNTHETIC_2026010106_012_002").write_bytes(b"OTHER ORIGIN")
    omitted = {k: v for k, v in a.items() if k not in {"step", "valid_time"}}
    assert discover_paths(config, [omitted]) == (selected,)
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


def test_reps_next_archive_day_keeps_cycle_lead_and_member(tmp_path):
    config = plan_source_binding(
        {"kind": "local", "dataset": "cma_reps", "root": str(tmp_path)}
    )
    archive = tmp_path / "ORIG-DATA/NAFP/CMA-REPS"
    prefix = "Z_NAFP_C_BABJ_20261231120000_P_NWPC-GRAPES-REPS-CN"
    fallback = archive / f"2027/20270101/{prefix}-00600-m001.grib2"
    fallback.parent.mkdir(parents=True)
    fallback.write_bytes(b"SYNTHETIC")
    other_member = fallback.with_name(f"{prefix}-00600-m002.grib2")
    other_member.write_bytes(b"SYNTHETIC")
    query = {"time": "2026-12-31T12:00:00Z", "member": 1}
    assert discover_paths(config, [{**query, "step": "PT6H"}]) == (fallback,)
    assert discover_paths(config, [query]) == (fallback,)

    primary = archive / f"2026/20261231/{fallback.name}"
    primary.parent.mkdir(parents=True)
    primary.write_bytes(b"SYNTHETIC")
    assert discover_paths(config, [{**query, "step": "PT6H"}]) == (primary,)
    assert discover_paths(config, [query]) == (primary,)
    assert discover_paths(config, [{"time": query["time"], "step": "PT6H"}]) == (
        primary, other_member
    )


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
