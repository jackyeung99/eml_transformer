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