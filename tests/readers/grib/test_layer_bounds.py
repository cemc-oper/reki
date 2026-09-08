import eccodes
import numpy as np

from reki.readers.grib.reader import GribReader


def _write_soil_layers(path):
    with path.open("wb") as output:
        for level, top, bottom in ((1, 0, 1), (2, 1, 2)):
            message = eccodes.codes_grib_new_from_samples("GRIB2")
            try:
                eccodes.codes_set(message, "typeOfLevel", "soilLayer")
                eccodes.codes_set(message, "level", level)
                eccodes.codes_set(message, "topLevel", top)
                eccodes.codes_set(message, "bottomLevel", bottom)
                eccodes.codes_write(message, output)
            finally:
                eccodes.codes_release(message)


def test_soil_layer_bounds_are_public_in_metadata_and_xarray(tmp_path):
    path = tmp_path / "soil-layers.grib2"
    _write_soil_layers(path)

    reader = GribReader(None, path, index_policy="off")
    fields = reader.all()
    assert [field.metadata.extra["layer_top"] for field in fields] == [0, 1]
    assert [field.metadata.extra["layer_bottom"] for field in fields] == [1, 2]
    assert reader.where(layer_top=0).one().metadata.level == 1
    assert reader.where(layer_top=3).one_or_none() is None

    index_dir = tmp_path / "index"
    GribReader(None, path, index_policy="auto", index_dir=index_dir).all()
    indexed = GribReader(None, path, index_policy="auto", index_dir=index_dir).all()
    assert [field.metadata.extra["layer_top"] for field in indexed] == [0, 1]
    assert [field.metadata.extra["layer_bottom"] for field in indexed] == [1, 2]

    data = reader.to_xarray()
    assert data.soilLayer.values.tolist() == [1, 2]
    np.testing.assert_array_equal(data.soilLayer_bounds.values, [[0, 1], [1, 2]])
    assert data.soilLayer.attrs["bounds"] == "soilLayer_bounds"
    assert data.soilLayer_bounds.attrs["units"] == "m"
