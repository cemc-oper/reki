import eccodes

from reki.readers.grib.index import IndexStore, index_path_for


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
