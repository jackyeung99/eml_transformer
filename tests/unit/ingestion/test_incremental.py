from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import pytest

import eml_transformer.ingestion.incremental as incremental_module
from eml_transformer.ingestion.incremental import (
    ingest_window,
    resolve_incremental_start,
    run_incremental_ingestion,
    validate_bronze_records,
)
from eml_transformer.ingestion.results import (
    IngestionResult,
)
from eml_transformer.schema.records import BronzeRecord


UTC = timezone.utc

TO_DATE = datetime(
    2026,
    1,
    10,
    tzinfo=UTC,
)


def make_bronze_record(
    *,
    record_id: str = "record-1",
    source: str = "fake",
) -> BronzeRecord:
    return BronzeRecord(
        source=source,
        record_id=record_id,
        published_at=TO_DATE,
        retrieved_at=TO_DATE,
        raw={
            "text": "Test record",
        },
    )


def test_resolve_start_without_checkpoint():
    result = resolve_incremental_start(
        checkpoint=None,
        lookback_days=3,
        to_date=TO_DATE,
    )

    assert result == TO_DATE - timedelta(days=3)


def test_resolve_start_uses_checkpoint_with_lookback():
    checkpoint_date = datetime(
        2026,
        1,
        8,
        tzinfo=UTC,
    )

    result = resolve_incremental_start(
        checkpoint={
            "last_checkpoint_value": (
                checkpoint_date.isoformat()
            )
        },
        lookback_days=2,
        to_date=TO_DATE,
    )

    assert result == checkpoint_date - timedelta(
        days=2
    )


def test_resolve_start_rejects_negative_lookback():
    with pytest.raises(
        ValueError,
        match="cannot be negative",
    ):
        resolve_incremental_start(
            checkpoint=None,
            lookback_days=-1,
            to_date=TO_DATE,
        )


def test_validate_bronze_records_rejects_missing_id():
    records = [
        make_bronze_record(record_id=""),
    ]

    with pytest.raises(
        ValueError,
        match="without a record_id",
    ):
        validate_bronze_records(
            records,
            expected_source="fake",
        )


def test_ingest_window_fetches_and_writes_records(
    storage,
    paths,
):
    records = [
        make_bronze_record(
            record_id="record-1",
        ),
        make_bronze_record(
            record_id="record-2",
        ),
    ]

    source = SimpleNamespace()
    source.fetch_calls = []

    def fetch_records(
        *,
        from_date: datetime,
        to_date: datetime,
    ) -> list[BronzeRecord]:
        source.fetch_calls.append(
            {
                "from_date": from_date,
                "to_date": to_date,
            }
        )
        return records

    source.fetch_records = fetch_records

    storage.write_bronze = lambda **kwargs: (
        SimpleNamespace(
            records_received=2,
            records_written=2,
            records_skipped=0,
        )
    )

    from_date = TO_DATE - timedelta(days=1)

    result = ingest_window(
        source=source,
        source_name="fake",
        storage=storage,
        paths=paths,
        from_date=from_date,
        to_date=TO_DATE,
    )

    assert result.status == "success"
    assert result.source == "fake"
    assert result.from_date == from_date
    assert result.to_date == TO_DATE
    assert result.records_fetched == 2
    assert result.records_written == 2
    assert result.records_skipped == 0

    assert source.fetch_calls == [
        {
            "from_date": from_date,
            "to_date": TO_DATE,
        }
    ]


def test_incremental_uses_checkpoint_and_updates_it(
    monkeypatch: pytest.MonkeyPatch,
    storage,
    paths,
):
    checkpoint_date = datetime(
        2026,
        1,
        8,
        tzinfo=UTC,
    )
    checkpoint_key = paths.checkpoint_key("fake")

    storage.write_checkpoint(
        checkpoint_key,
        {
            "source": "fake",
            "last_checkpoint_value": checkpoint_date,
        },
    )

    expected_from_date = checkpoint_date - timedelta(
        days=2
    )

    calls: list[dict[str, Any]] = []

    def fake_ingest_window(
        **kwargs: Any,
    ) -> IngestionResult:
        calls.append(kwargs)

        return IngestionResult(
            status="success",
            source="fake",
            reason="Ingestion completed",
            from_date=kwargs["from_date"],
            to_date=kwargs["to_date"],
            records_fetched=10,
            records_written=8,
            records_skipped=2,
        )

    monkeypatch.setattr(
        incremental_module,
        "ingest_window",
        fake_ingest_window,
    )

    result = run_incremental_ingestion(
        source=object(),
        source_name="fake",
        source_config={
            "ingestion": {
                "lookback_days": 2,
            }
        },
        storage=storage,
        paths=paths,
        to_date=TO_DATE,
    )

    assert result.status == "success"

    assert calls[0]["from_date"] == expected_from_date
    assert calls[0]["to_date"] == TO_DATE

    checkpoint = storage.read_checkpoint(
        checkpoint_key
    )

    assert checkpoint == {
        "source": "fake",
        "last_checkpoint_value": TO_DATE,
    }


def test_incremental_does_not_checkpoint_failure(
    monkeypatch: pytest.MonkeyPatch,
    storage,
    paths,
):
    checkpoint_key = paths.checkpoint_key("fake")

    monkeypatch.setattr(
        incremental_module,
        "ingest_window",
        lambda **kwargs: IngestionResult(
            status="failure",
            source="fake",
            reason="Fetch failed",
            from_date=kwargs["from_date"],
            to_date=kwargs["to_date"],
            records_fetched=0,
            records_written=0,
            records_skipped=0,
            error="API unavailable",
        ),
    )

    result = run_incremental_ingestion(
        source=object(),
        source_name="fake",
        source_config={
            "ingestion": {
                "lookback_days": 1,
            }
        },
        storage=storage,
        paths=paths,
        to_date=TO_DATE,
    )

    assert result.status == "failure"
    assert storage.read_checkpoint(
        checkpoint_key
    ) is None