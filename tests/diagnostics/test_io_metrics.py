from reki.diagnostics import collect_io_metrics, record_io_event


def test_snapshot_is_silent_immutable_and_nested_context_owns_events():
    record_io_event("file_open_count")
    with collect_io_metrics() as outer:
        record_io_event("file_open_count")
        with collect_io_metrics() as inner:
            record_io_event("value_decode_count")
        record_io_event("grib_header_scan_count")
    assert outer.snapshot().to_dict()["file_open_count"] == 1
    assert outer.snapshot().to_dict()["grib_header_scan_count"] == 1
    assert outer.snapshot().to_dict()["value_decode_count"] == 0
    assert inner.snapshot().to_dict()["value_decode_count"] == 1
    snapshot = outer.snapshot()
    try:
        snapshot.counters["file_open_count"] = 2
    except TypeError:
        pass
    else:
        raise AssertionError("snapshot counters must be immutable")
