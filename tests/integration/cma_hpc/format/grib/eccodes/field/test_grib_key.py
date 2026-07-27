from reki.format.grib.eccodes import load_field_from_file



def test_max(meso_grib2_orig_file_path):
    field = load_field_from_file(
        meso_grib2_orig_file_path,
        parameter="UGRD",
        level_type="heightAboveGround",
        level=10,
        stepType="instant",
    )
    assert field is not None
    assert field.attrs["GRIB_count"] == 9

    field = load_field_from_file(
        meso_grib2_orig_file_path,
        parameter="UGRD",
        level_type="heightAboveGround",
        level=10,
        stepType="max",
    )
    assert field is not None
    assert field.attrs["GRIB_count"] == 20
