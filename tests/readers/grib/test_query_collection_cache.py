"""T12 bounded native field reuse and batch I/O counts."""

import importlib.util
import os
import shutil
from pathlib import Path

import numpy as np
import pytest

from reki.catalog import load_catalog
from reki.catalog.query_binding import CatalogSnapshot, plan_source_binding
from reki.diagnostics import collect_io_metrics
from reki.query_collection import CollectionRequest, CollectionSession, read_grib_collection
from reki.query_locator import verify_data_reference
from cedarkit_query import QueryError


@pytest.fixture(scope="module")
def assets(tmp_path_factory):
    script = Path(__file__).resolve().parents[2] / "fixtures/t09/generate.py"
    spec = importlib.util.spec_from_file_location("t12_assets", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = tmp_path_factory.mktemp("t12-grib")
    module.build(root)
    return root


def _plan(root, *, lead=0, level=500, member=1, version="t12-catalog", pattern="baseline/f{forecast_hour_label}_m1.grib2"):
    catalog = load_catalog(builtin=False, plugins=False, user=False, explicit={
        "api_version": "reki.catalog/v1", "datasets": [{"id": "grid", "source": {
            "name": "file-pattern", "args": [str(root), pattern]}}]})
    query = {"api_version": "cedarkit.query/v1", "domain": "grid", "dataset": "grid",
             "parameter": "cedarkit.t", "reference_time": "2026-08-30T00:00:00Z",
             "lead_time": f"PT{lead * 3600}S",
             "vertical": {"type": "isobaric", "unit": "Pa", "values": level * 100},
             "member": {"id": str(member), "role": "control" if member == 0 else "perturbation"},
             "statistic": {"kind": "instant"}}
    return plan_source_binding(query, snapshot=CatalogSnapshot(catalog, version))


def _job(plan, path):
    return CollectionRequest(plan, (path,), {"cedarkit.t": "t"},
                             {"0": "control", "1": "perturbation", "2": "perturbation"})


def test_batch_reuses_one_scan_and_each_unique_field_once(assets, tmp_path):
    path = assets / "baseline/f000_m1.grib2"
    low, high = _job(_plan(assets, level=500), path), _job(_plan(assets, level=850), path)
    with collect_io_metrics() as sequential:
        for job in (low, low, high):
            read_grib_collection(job.plan, candidate_paths=job.candidate_paths,
                                 native_parameters=job.native_parameters, member_roles=job.member_roles,
                                 index_policy="off")
    assert sequential.snapshot()["grib_header_scan_count"] == 6
    assert sequential.snapshot()["value_decode_count"] == 3
    assert sequential.snapshot()["file_open_count"] == 6
    with CollectionSession(index_policy="off") as session:
        with collect_io_metrics() as batched:
            results = session.read_many((low, low, high))
        cold = batched.snapshot()
        assert cold["grib_header_scan_count"] == 2
        assert cold["value_decode_count"] == 2
        assert cold["file_open_count"] == 3
        assert cold["file_open_count"] < sequential.snapshot()["file_open_count"]
        assert cold["value_decode_count"] < sequential.snapshot()["value_decode_count"]
        np.testing.assert_array_equal(results[0].data.values, results[1].data.values)
        assert not np.array_equal(results[0].data.values, results[2].data.values)
        with collect_io_metrics() as hot:
            session.read_many((low, high))
        assert hot.snapshot()["grib_header_scan_count"] == 0
        assert hot.snapshot()["file_open_count"] == 0
        assert hot.snapshot()["value_decode_count"] == 0
        assert session.cache_info().metadata_hits >= 4
        assert session.cache_info().value_hits >= 3
        results[0].fields[0].data.values[0, 0] = -999
        again = session.read(low.plan, candidate_paths=low.candidate_paths,
                             native_parameters=low.native_parameters, member_roles=low.member_roles)
        assert again.fields[0].data.values[0, 0] != -999

    index_dir = tmp_path / "index"
    with CollectionSession(index_dir=index_dir) as cold_session:
        with collect_io_metrics() as cold_index:
            cold_session.read_many((low, high))
    assert cold_index.snapshot()["index_build_count"] == 1
    assert cold_index.snapshot()["grib_header_scan_count"] == 2
    with CollectionSession(index_dir=index_dir) as warm_session:
        with collect_io_metrics() as warm_index:
            warm_session.read_many((low, high))
    assert warm_index.snapshot()["index_hit_count"] >= 1
    assert warm_index.snapshot()["grib_header_scan_count"] == 0
    assert warm_index.snapshot()["value_decode_count"] == 2


def test_capacity_eviction_and_independent_returned_arrays(assets):
    first = _job(_plan(assets, lead=0), assets / "baseline/f000_m1.grib2")
    second = _job(_plan(assets, lead=6), assets / "baseline/f006_m1.grib2")
    with CollectionSession(max_resources=1, max_fields=2, max_bytes=96,
                           index_policy="off") as session:
        original = session.read(first.plan, candidate_paths=first.candidate_paths,
                                native_parameters=first.native_parameters, member_roles=first.member_roles)
        original_value = float(original.data.values[0, 0, 0, 0, 0])
        session.read(second.plan, candidate_paths=second.candidate_paths,
                     native_parameters=second.native_parameters, member_roles=second.member_roles)
        assert session.cache_info().resources == 1
        assert session.cache_info().metadata_fields <= 2
        assert session.cache_info().value_bytes <= 96
        assert session.cache_info().evictions >= 1
        with collect_io_metrics() as metrics:
            session.read(first.plan, candidate_paths=first.candidate_paths,
                         native_parameters=first.native_parameters, member_roles=first.member_roles)
        assert metrics.snapshot()["grib_header_scan_count"] == 2
        session.clear()
        assert session.cache_info().resources == 0
    assert original.data.values[0, 0, 0, 0, 0] == original_value
    assert session.cache_info().closed
    with pytest.raises(RuntimeError, match="closed"):
        session.read(first.plan, candidate_paths=first.candidate_paths,
                     native_parameters=first.native_parameters, member_roles=first.member_roles)


def test_oversize_value_is_not_cached_but_metadata_is(assets):
    job = _job(_plan(assets), assets / "baseline/f000_m1.grib2")
    with CollectionSession(max_bytes=1, index_policy="off") as session:
        with collect_io_metrics() as metrics:
            session.read_many((job, job))
        assert metrics.snapshot()["grib_header_scan_count"] == 2
        assert metrics.snapshot()["value_decode_count"] == 2
        assert session.cache_info().resources == 1
        assert session.cache_info().value_bytes == 0


def test_metadata_field_limit_and_binding_version_do_not_cache_derived_results(assets):
    path = assets / "baseline/f000_m1.grib2"
    old = _job(_plan(assets, version="catalog-a"), path)
    new = _job(_plan(assets, version="catalog-b"), path)
    with CollectionSession(max_fields=1, index_policy="off") as tiny:
        with collect_io_metrics() as metrics:
            tiny.read_many((old, old))
        assert metrics.snapshot()["grib_header_scan_count"] == 4
        assert tiny.cache_info().resources == 0
    with CollectionSession(index_policy="off") as session:
        with collect_io_metrics() as metrics:
            results = session.read_many((old, new))
        assert metrics.snapshot()["grib_header_scan_count"] == 2
        assert metrics.snapshot()["value_decode_count"] == 1
        assert results[0].fields[0].reference.binding_id != results[1].fields[0].reference.binding_id
        assert results[0].data.attrs["source_references"] != results[1].data.attrs["source_references"]


def test_replaced_resource_invalidates_offset_and_value_cache(assets, tmp_path):
    active = tmp_path / "active.grib2"
    shutil.copyfile(assets / "baseline/f042_m0.grib2", active)
    job = _job(_plan(tmp_path, lead=42, member=0, pattern="active.grib2"), active)
    with CollectionSession(index_policy="off") as session:
        before = session.read(job.plan, candidate_paths=job.candidate_paths,
                              native_parameters=job.native_parameters, member_roles=job.member_roles)
        replacement = tmp_path / "replacement.grib2"
        shutil.copyfile(assets / "cases/resource_updated.grib2", replacement)
        replacement.replace(active)
        with pytest.raises(QueryError) as stale:
            verify_data_reference(before.fields[0].reference)
        assert stale.value.code == "stale_reference"
        with collect_io_metrics() as metrics:
            after = session.read(job.plan, candidate_paths=job.candidate_paths,
                                 native_parameters=job.native_parameters, member_roles=job.member_roles)
        assert metrics.snapshot()["grib_header_scan_count"] == 2
        assert metrics.snapshot()["value_decode_count"] == 1
        assert after.data.values[0, 0, 0, 0, 0] == before.data.values[0, 0, 0, 0, 0] + 10
        assert session.cache_info().evictions >= 1


def test_sha256_invalidates_same_stat_rewrite(assets, tmp_path):
    active = tmp_path / "active.grib2"
    shutil.copyfile(assets / "baseline/f042_m0.grib2", active)
    job = _job(_plan(tmp_path, lead=42, member=0, pattern="active.grib2"), active)
    with CollectionSession(index_policy="off", hash_resources=True) as session:
        before = session.read(job.plan, candidate_paths=job.candidate_paths,
                              native_parameters=job.native_parameters, member_roles=job.member_roles)
        stat = active.stat()
        active.write_bytes((assets / "cases/resource_updated.grib2").read_bytes())
        os.utime(active, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        assert active.stat().st_size == stat.st_size
        assert active.stat().st_ino == stat.st_ino
        with collect_io_metrics() as metrics:
            after = session.read(job.plan, candidate_paths=job.candidate_paths,
                                 native_parameters=job.native_parameters, member_roles=job.member_roles)
        assert metrics.snapshot()["value_decode_count"] == 1
        assert after.fields[0].data.values[0, 0] == before.fields[0].data.values[0, 0] + 10
        assert session.cache_info().evictions >= 1


@pytest.mark.parametrize("failure", [ValueError, KeyboardInterrupt])
def test_failure_and_cancellation_release_message_and_session(assets, monkeypatch, failure):
    from reki import query_collection as collection

    job = _job(_plan(assets), assets / "baseline/f000_m1.grib2")
    releases = []
    original_release = collection.eccodes.codes_release

    def release(message):
        releases.append(message)
        return original_release(message)

    def cancelled(message):
        raise failure("decode stopped")

    monkeypatch.setattr(collection.eccodes, "codes_release", release)
    original_create = collection.create_data_array_from_message
    with CollectionSession(index_policy="off") as session:
        monkeypatch.setattr(collection, "create_data_array_from_message", cancelled)
        expected = KeyboardInterrupt if failure is KeyboardInterrupt else QueryError
        with pytest.raises(expected) as caught:
            session.read(job.plan, candidate_paths=job.candidate_paths,
                         native_parameters=job.native_parameters, member_roles=job.member_roles)
        if failure is ValueError:
            assert caught.value.code == "provider_error"
        assert releases
        assert session.cache_info().value_bytes == 0
        monkeypatch.setattr(collection, "create_data_array_from_message", original_create)
        result = session.read(job.plan, candidate_paths=job.candidate_paths,
                              native_parameters=job.native_parameters, member_roles=job.member_roles)
        assert result.complete
    assert session.cache_info().closed
