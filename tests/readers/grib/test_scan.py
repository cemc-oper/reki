import eccodes

from reki.diagnostics import collect_io_metrics
from reki import resolve_parameter
from reki.readers.grib.eccodes._check import _check_message
from reki.readers.grib.eccodes._decode import load_message_at_offset
from reki.readers.grib.eccodes._scan import iter_headers


def test_headers_are_observed_released_and_locatable(grib2_gfs_basic_file_path):
    with collect_io_metrics() as metrics:
        iterator = iter_headers(grib2_gfs_basic_file_path)
        first = next(iterator)
        offset = first.offset
        assert first.ordinal == 0
        iterator.close()
        assert first.handle is None
        message = load_message_at_offset(grib2_gfs_basic_file_path, offset, headers_only=True)
        try:
            assert eccodes.codes_get(message, "shortName")
        finally:
            eccodes.codes_release(message)
    snapshot = metrics.snapshot()
    assert snapshot["grib_header_scan_count"] == 1
    assert snapshot["file_open_count"] == 2


def test_resolved_variant_first_level_matches_header(grib2_gfs_basic_file_path):
    """Registry ``first_level`` conditions stay aliases, never GRIB keys."""
    query = resolve_parameter("cedarkit.t2m").query
    headers = iter_headers(grib2_gfs_basic_file_path)
    try:
        for header in headers:
            if header.ordinal == 24:
                assert _check_message(
                    header.handle, dict(query.parameter), query.level_type, query.level,
                    **dict(query.extra),
                )
                break
        else:
            raise AssertionError("the fixed GFS fixture has no 2 m temperature message")
    finally:
        headers.close()
