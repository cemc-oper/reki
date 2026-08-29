import multiprocessing

import eccodes

from reki.diagnostics import collect_io_metrics
from reki.readers.grib.index import IndexStore, index_path_for
from reki.readers.grib.reader import GribReader


def _write(path, levels=(850, 500)):
    with path.open("wb") as file_handle:
        for level in levels:
            message = eccodes.codes_grib_new_from_samples("GRIB2")
            try:
                eccodes.codes_set(message, "shortName", "t")
                eccodes.codes_set(message, "typeOfLevel", "isobaricInhPa")
                eccodes.codes_set(message, "level", level)
                eccodes.codes_write(message, file_handle)
            finally:
                eccodes.codes_release(message)


def _concurrent_open(source, root, queue):
    """Spawn-safe worker used to verify the on-disk advisory lock."""
    with collect_io_metrics() as metrics:
        fields = GribReader(None, source, index_dir=root).all()
        queue.put((len(fields), metrics.snapshot().to_dict()))


def test_build_open_and_invalidate_without_touching_source(tmp_path):
    source = tmp_path / "field with space.grib"
    root = tmp_path / "indexes"
    _write(source)
    store = IndexStore(source, index_dir=root)
    connection = store.build()
    assert connection.execute("select count(*) from fields").fetchone()[0] == 2
    connection.close()
    assert store.path.parent == root
    assert store.path == index_path_for(source, root)
    connection = store.open_valid()
    assert connection is not None
    connection.close()
    with source.open("ab") as file_handle:
        file_handle.write(b"padding")
    assert store.open_valid() is None


def test_two_processes_publish_one_valid_initial_index(tmp_path):
    source = tmp_path / "fields.grib"
    root = tmp_path / "indexes"
    _write(source)
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    workers = [context.Process(target=_concurrent_open, args=(str(source), str(root), queue))
               for _ in range(2)]
    for worker in workers:
        worker.start()
    results = [queue.get(timeout=30) for _ in workers]
    for worker in workers:
        worker.join(30)
        assert worker.exitcode == 0
    assert [size for size, _ in results] == [2, 2]
    assert sum(snapshot["index_build_count"] for _, snapshot in results) == 1
    connection = IndexStore(source, index_dir=root).open_valid()
    assert connection is not None
    connection.close()
