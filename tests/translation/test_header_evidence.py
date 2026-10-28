"""Scalar evidence tests use generated messages and forbid every array API."""

import hashlib

import eccodes
import pytest

from cedarkit_query import SourceError
from reki.translation.header_evidence import (
    collect_headers,
    digest_file,
    inspect_header,
    scalar_field,
    time_descriptors,
    read_section4,
)


@pytest.fixture
def no_arrays(monkeypatch):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(args)
        raise AssertionError("scalar-only header test requested an array")

    for name in (
        "codes_get_values",
        "codes_get_array",
        "codes_get_double_array",
        "codes_get_long_array",
        "codes_get_string_array",
        "codes_grib_get_data",
    ):
        if hasattr(eccodes, name):
            monkeypatch.setattr(eccodes, name, forbidden)
    return calls


@pytest.fixture
def handle():
    h = eccodes.codes_grib_new_from_samples("regular_ll_sfc_grib2")
    eccodes.codes_set_long(h, "centre", 38)
    try:
        yield h
    finally:
        eccodes.codes_release(h)


@pytest.fixture
def encoded_file(tmp_path, handle):
    path = tmp_path / "SYNTHETIC.headers.grib2"
    with path.open("wb") as stream:
        for hour in (0, 6, 12):
            eccodes.codes_set_long(handle, "forecastTime", hour)
            eccodes.codes_write(handle, stream)
    return path


def test_missing_undefined_and_real_zero_never_collapse_to_default(handle, no_arrays):
    record = inspect_header(handle)
    fields = record["fields"]
    assert fields["centre"] == {"state": "present", "value": 38}
    assert fields["localTablesVersion"] == {"state": "present", "value": 0}
    assert fields["derivedForecast"] == {"state": "undefined", "value": None}
    assert fields["scaleFactorOfSecondFixedSurface"] == {
        "state": "missing",
        "value": None,
    }
    assert record["time_descriptors"] == []
    assert not no_arrays


def test_typed_getter_error_is_evidence_not_zero(handle, no_arrays, monkeypatch):
    original = eccodes.codes_get_long

    def fail(h, key):
        return (
            original(h, "SYNTHETIC_UNDEFINED_KEY")
            if key == "centre"
            else original(h, key)
        )

    monkeypatch.setattr(eccodes, "codes_get_long", fail)
    item = scalar_field(handle, "centre", "integer")
    assert item["state"] == "getter_error" and item["value"] is None
    assert item["error_type"] == "KeyValueNotFoundError"
    assert not no_arrays


@pytest.mark.parametrize(
    "key,kind",
    [
        ("values", "integer"),
        ("latitudes", "string"),
        ("Ni", "string"),
        ("#0#lengthOfTimeRange", "integer"),
        ("#1#values", "integer"),
        ("#1#lengthOfTimeRange", "integer"),
    ],
)
def test_whitelist_cannot_be_used_to_read_values(handle, no_arrays, key, kind):
    with pytest.raises(ValueError, match="whitelist"):
        scalar_field(handle, key, kind)
    assert not no_arrays


def test_repeated_time_descriptors_preserve_raw_order(handle, no_arrays, tmp_path):
    eccodes.codes_set_long(handle, "productDefinitionTemplateNumber", 8)
    eccodes.codes_set_long(handle, "numberOfTimeRange", 2)
    path = tmp_path / "SYNTHETIC.interval.grib2"
    with path.open("wb") as stream:
        eccodes.codes_write(handle, stream)
    section = bytearray(read_section4(path, 0))
    section[46], section[58] = 0, 2
    record = inspect_header(handle, bytes(section))
    assert record["fields"]["numberOfTimeRange"]["value"] == 2
    assert record["fields"]["typeOfStatisticalProcessing"] == {
        "state": "multiple",
        "value": None,
    }
    assert record["fields"]["lengthOfTimeRange"] == {"state": "multiple", "value": None}
    assert len(record["time_descriptors"]) == 2
    assert [
        r["typeOfStatisticalProcessing"]["value"] for r in record["time_descriptors"]
    ] == [0, 2]
    assert not no_arrays


@pytest.mark.parametrize("template,count_at,start", [(8, 41, 46), (11, 44, 49)])
def test_descriptor_octets_and_optional_coordinates(template, count_at, start):
    section = bytearray(start + 24 + 4)
    section[:4] = len(section).to_bytes(4, "big")
    section[4], section[6], section[8], section[count_at] = 4, 1, template, 2
    section[start : start + 12] = bytes([2, 2, 1, 0, 0, 0, 6, 1, 0, 0, 0, 1])
    section[start + 12 : start + 24] = bytes([0, 1, 1, 0, 0, 0, 12, 1, 0, 0, 0, 3])
    result, status = time_descriptors(section)
    assert status == "raw_section4_verified"
    assert [r["lengthOfTimeRange"]["value"] for r in result] == [6, 12]
    assert [r["timeIncrement"]["value"] for r in result] == [1, 3]
    section[6] = 0
    with pytest.raises(ValueError, match="length mismatch"):
        time_descriptors(section)


def test_reader_rejects_non_header_sections_and_truncation(tmp_path):
    path = tmp_path / "SYNTHETIC.malformed"
    path.write_bytes(
        b"GRIB"
        + bytes([0, 0, 0, 2])
        + (25).to_bytes(8, "big")
        + (5).to_bytes(4, "big")
        + bytes([7])
        + b"7777"
    )
    with pytest.raises(ValueError, match="not found"):
        read_section4(path, 0)
    path.write_bytes(b"GRIB")
    with pytest.raises(ValueError, match="indicator"):
        read_section4(path, 0)


def test_byte_hash_and_selected_offsets_match_independent_expectations(
    encoded_file, no_arrays
):
    proof = digest_file(encoded_file)
    assert proof["sha256"] == hashlib.sha256(encoded_file.read_bytes()).hexdigest()
    found = collect_headers(encoded_file, [0, 2], fingerprint=proof["fingerprint"])
    assert found["missing_positions"] == [] and found["container_headers_visited"] == 3
    assert [r["fields"]["forecastTime"]["value"] for r in found["records"]] == [0, 12]
    assert [r["message_index"] for r in found["records"]] == [0, 2]
    assert found["records"][0]["stream_offset"] == 0
    assert (
        found["records"][1]["stream_offset"]
        == 2 * found["records"][0]["message_length"]
    )
    assert not no_arrays and found["value_arrays_requested"] == 0


def test_new_generation_cannot_reuse_digest_proof(encoded_file, no_arrays):
    proof = digest_file(encoded_file)
    with encoded_file.open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(SourceError) as exc:
        collect_headers(encoded_file, [0], fingerprint=proof["fingerprint"])
    assert exc.value.context["reason"] == "resource_changed"
    assert not no_arrays


@pytest.mark.parametrize("positions", [[], [-1], [True], [1, True]])
def test_positions_are_explicit_and_integer_only(encoded_file, positions):
    with pytest.raises(ValueError):
        collect_headers(encoded_file, positions)


def test_missing_position_is_not_silently_reported_as_found(encoded_file, no_arrays):
    result = collect_headers(encoded_file, [99])
    assert result["records"] == [] and result["missing_positions"] == [99]
    assert result["container_headers_visited"] == 3
    assert not no_arrays
