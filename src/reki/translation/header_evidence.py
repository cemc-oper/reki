"""Internal, scalar-only GRIB header evidence; no business selection or values.

Hashing reads encoded bytes without unpacking. Header collection uses only a
finite scalar whitelist and keeps undefined/missing/getter-error states distinct.
"""

import hashlib
from pathlib import Path

from reki.grib_io import iter_headers
from reki.selection.files import FileSnapshot
from .grib_backend import INTEGER_KEYS, GRID_INTEGER_KEYS, STRING_KEYS

RANGE_KEYS = (
    "typeOfStatisticalProcessing",
    "typeOfTimeIncrement",
    "indicatorOfUnitForTimeRange",
    "lengthOfTimeRange",
    "indicatorOfUnitForTimeIncrement",
    "timeIncrement",
)
INTEGER_FIELDS = (
    INTEGER_KEYS | GRID_INTEGER_KEYS | frozenset(RANGE_KEYS) | {"totalLength"}
)
STRING_FIELDS = STRING_KEYS | {"md5GridSection"}


def scalar_field(handle, key, kind):
    import eccodes

    allowed = (kind == "integer" and key in INTEGER_FIELDS) or (
        kind == "string" and key in STRING_FIELDS
    )
    if not allowed:
        raise ValueError("only the finite scalar header whitelist is allowed")
    try:
        if not eccodes.codes_is_defined(handle, key):
            return {"state": "undefined", "value": None}
        if kind == "integer" and eccodes.codes_get_size(handle, key) != 1:
            return {"state": "multiple", "value": None}
        if eccodes.codes_is_missing(handle, key):
            return {"state": "missing", "value": None}
        value = (
            eccodes.codes_get_long if kind == "integer" else eccodes.codes_get_string
        )(handle, key)
        return {"state": "present", "value": value}
    except eccodes.CodesInternalError as exc:
        return {
            "state": "getter_error",
            "value": None,
            "error_type": type(exc).__name__,
        }


def read_section4(path, offset):
    """Read section 4 only; seek past earlier sections, never into packed values."""
    with Path(path).open("rb") as stream:
        stream.seek(offset)
        indicator = stream.read(16)
        if len(indicator) != 16 or indicator[:4] != b"GRIB" or indicator[7] != 2:
            raise ValueError("expected GRIB edition 2 indicator")
        end = offset + int.from_bytes(indicator[8:16], "big") - 4
        while stream.tell() < end:
            start = stream.tell()
            header = stream.read(5)
            size = int.from_bytes(header[:4], "big")
            if len(header) != 5 or size < 5 or start + size > end:
                raise ValueError("invalid section length")
            if header[4] == 4:
                if size > 1024 * 1024:
                    raise ValueError("section 4 exceeds evidence reader bound")
                body = stream.read(size - 5)
                if len(body) != size - 5:
                    raise ValueError("truncated section 4")
                return header + body
            if header[4] not in (1, 2, 3):
                break
            stream.seek(start + size)
    raise ValueError("section 4 not found before packed data")


def time_descriptors(section):
    """Raw repeated descriptors for the two interval templates in the manifest.

    ECMWF GRIB2 template 4.8 octets 42/47 and 4.11 octets 45/50.
    No ecCodes ranked-key syntax or array getters are used.
    """
    if len(section) < 9 or section[4] != 4:
        raise ValueError("invalid section 4")
    if int.from_bytes(section[:4], "big") != len(section):
        raise ValueError("section 4 length mismatch")
    template = int.from_bytes(section[7:9], "big")
    offsets = {8: (41, 46), 11: (44, 49)}
    if template not in offsets:
        return [], "not_applicable_or_unreviewed_template"
    count_at, start = offsets[template]
    if len(section) < start:
        raise ValueError("truncated interval template")
    count = section[count_at]
    coordinates = int.from_bytes(section[5:7], "big")
    if start + 12 * count + 4 * coordinates != len(section):
        raise ValueError("interval descriptor length mismatch")
    records = []
    for position in range(start, start + 12 * count, 12):
        raw = section[position : position + 12]
        values = (
            raw[0],
            raw[1],
            raw[2],
            int.from_bytes(raw[3:7], "big"),
            raw[7],
            int.from_bytes(raw[8:12], "big"),
        )
        records.append(
            {
                key: {"state": "present", "value": value, "origin": "section4_raw"}
                for key, value in zip(RANGE_KEYS, values, strict=True)
            }
        )
    return records, "raw_section4_verified"


def inspect_header(handle, section4=None):
    """No default integers and no unqualified repeated time descriptor values."""
    result = {
        key: scalar_field(handle, key, "integer") for key in sorted(INTEGER_FIELDS)
    }
    result.update(
        {key: scalar_field(handle, key, "string") for key in sorted(STRING_FIELDS)}
    )
    descriptors, status = (
        ([], "section4_not_supplied")
        if section4 is None
        else time_descriptors(section4)
    )
    if status == "raw_section4_verified":
        count = result["numberOfTimeRange"]
        if count != {"state": "present", "value": len(descriptors)}:
            raise ValueError("native and raw descriptor counts disagree")
    return {
        "fields": result,
        "time_descriptors": descriptors,
        "time_descriptor_status": status,
    }


def digest_file(path):
    """Pin and SHA-256 encoded bytes, without interpreting packed data."""
    snapshot = FileSnapshot.capture(path)
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            hasher.update(block)
    snapshot.verify()
    return {
        "sha256": hasher.hexdigest(),
        "size": snapshot.fingerprint[2],
        "fingerprint": list(snapshot.fingerprint),
    }


def collect_headers(path, positions, *, fingerprint=None):
    """Walk only to requested ordinals; no parameter resolution or grid/value arrays."""
    positions = tuple(positions)
    if not positions or any(type(i) is not int or i < 0 for i in positions):
        raise ValueError("explicit nonnegative header positions required")
    wanted = set(positions)
    snapshot = (
        FileSnapshot.capture(path)
        if fingerprint is None
        else FileSnapshot(Path(path).absolute(), tuple(fingerprint))
    )
    snapshot.verify()
    records, visited = [], 0
    iterator = iter_headers(path, headers_only=True)
    try:
        for header in iterator:
            visited += 1
            if header.ordinal in wanted:
                records.append(
                    {
                        "message_index": header.ordinal,
                        "stream_offset": header.offset,
                        "message_length": header.message_length,
                        **inspect_header(
                            header.handle, read_section4(path, header.offset)
                        ),
                    }
                )
            if header.ordinal == max(wanted):
                break
    finally:
        iterator.close()
    snapshot.verify()
    return {
        "records": records,
        "container_headers_visited": visited,
        "requested_positions": sorted(wanted),
        "missing_positions": sorted(wanted - {r["message_index"] for r in records}),
        "fingerprint": list(snapshot.fingerprint),
        "value_arrays_requested": 0,
    }
