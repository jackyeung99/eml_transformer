from eml_transformer.ingestion.sources.gdelt import GDELTSource


def test_get_timestamps_single_day(gdelt_source):
    timestamps = gdelt_source._get_timestamps(
        "2026-01-01",
        "2026-01-01",
    )

    assert len(timestamps) == 96
    assert timestamps[0] == "20260101000000"
    assert timestamps[-1] == "20260101234500"

def test_get_timestamps_multiple_days(gdelt_source):
    timestamps = gdelt_source._get_timestamps(
        "2026-01-01",
        "2026-01-02",
    )

    assert len(timestamps) == 96 * 2

    assert timestamps[0] == "20260101000000"
    assert timestamps[1] == "20260101001500"
    assert timestamps[95] == "20260101234500"

    assert timestamps[96] == "20260102000000"
    assert timestamps[-1] == "20260102234500"

def test_get_timestamps_are_15_minutes_apart(gdelt_source):

    timestamps = gdelt_source._get_timestamps(
        "2026-01-01",
        "2026-01-01",
    )

    assert timestamps[0] == "20260101000000"
    assert timestamps[1] == "20260101001500"
    assert timestamps[2] == "20260101003000"
    assert timestamps[3] == "20260101004500"
    assert timestamps[4] == "20260101010000"

def test_get_timestamps_month_boundary(gdelt_source):
    timestamps = gdelt_source._get_timestamps(
        "2026-01-31",
        "2026-02-01",
    )

    assert len(timestamps) == 96 * 2
    assert timestamps[0] == "20260131000000"
    assert timestamps[95] == "20260131234500"
    assert timestamps[96] == "20260201000000"
    assert timestamps[-1] == "20260201234500"

def test_get_timestamps_year_boundary(gdelt_source):
    timestamps = gdelt_source._get_timestamps(
        "2025-12-31",
        "2026-01-01",
    )

    assert len(timestamps) == 96 * 2
    assert timestamps[0] == "20251231000000"
    assert timestamps[95] == "20251231234500"
    assert timestamps[96] == "20260101000000"
    assert timestamps[-1] == "20260101234500"

def test_get_timestamps_leap_day(gdelt_source):
    timestamps = gdelt_source._get_timestamps(
        "2024-02-28",
        "2024-03-01",
    )

    assert len(timestamps) == 96 * 3
    assert timestamps[0] == "20240228000000"
    assert timestamps[95] == "20240228234500"
    assert timestamps[96] == "20240229000000"
    assert timestamps[191] == "20240229234500"
    assert timestamps[192] == "20240301000000"
    assert timestamps[-1] == "20240301234500"