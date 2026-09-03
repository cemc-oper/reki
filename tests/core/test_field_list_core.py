import pytest
import pandas as pd

from reki import DataNotFoundError, FieldList, FieldMetadata, MultipleFieldsMatchedError


class Field:
    def __init__(self, metadata):
        self.metadata = metadata


def test_field_list_sequence_selection_cardinality_and_immutability():
    one = Field(FieldMetadata(0, 1, "t", "pl", 850, source="one.grib"))
    two = Field(FieldMetadata(1, 2, "u", "pl", 850, source="one.grib"))
    fields = FieldList([one, two])
    assert len(fields) == 2 and fields[-1] is two and len(fields[:1]) == 1
    assert fields.sel(parameter="t").one() is one
    assert fields.sel(parameter="v").first() is None
    with pytest.raises(DataNotFoundError):
        fields.sel(parameter="v").one()
    with pytest.raises(MultipleFieldsMatchedError):
        fields.one()
    with pytest.raises(TypeError):
        one.metadata.extra["x"] = 1
    assert len(FieldList.concat(fields, fields, deduplicate=True)) == 2


def test_metadata_returns_missing_values_for_extra_keys_not_on_every_field():
    fields = FieldList([
        Field(FieldMetadata(0, 1, "t", "pl", 850, extra={"wgrib2_name": "TMP"})),
        Field(FieldMetadata(1, 2, "u", "pl", 850)),
    ])

    metadata = fields.ls(("index", "wgrib2_name"))
    assert metadata["index"].tolist() == [0, 1]
    assert metadata["wgrib2_name"].iloc[0] == "TMP"
    assert pd.isna(metadata["wgrib2_name"].iloc[1])
