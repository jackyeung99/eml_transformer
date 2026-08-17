from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

import eml_transformer.ingestion.historical as historical_module
from eml_transformer.ingestion.historical import (
    iter_date_windows,
    run_historical_ingestion,
    summarize_historical_ingestion,
    validate_historical_source,
)
from eml_transformer.ingestion.results import (
    IngestionResult,
)


UTC = timezone.utc

START = datetime(
    2026,
    1,
    1,
    tzinfo=UTC,
)
END = datetime(
    2026,
    1,
    10,
    tzinfo=UTC,
)


def make_source(
    *,
    update_mode: str = "incremental",
    supports_backfill: bool = True,
):
    return SimpleNamespace(
        update_mode=update_mode,
        supports_backfill=supports_backfill,
    )


def make_ingestion_result(
    *,
    status: str = "success",
    fetched: int = 0,
    written: int = 0,
    skipped: int = 0,
    error: str | None = None,
) -> IngestionResult:
    return IngestionResult(
        status=status,
        source="fake",
        reason=(
            "Ingestion completed"
            if status == "success"
            else "Ingestion failed"
        ),
        records_fetched=fetched,
        records_written=written,
        records_skipped=skipped,
        error=error,
    )


class TestDateWindows:
    def test_splits_range_into_windows(self):
        windows = list(
            iter_date_windows(
                from_date=START,
                to_date=END,
                window_days=3,
            )
        )

        assert windows == [
            (
                datetime(
                    2026,
                    1,
                    1,
                    tzinfo=UTC,
                ),
                datetime(
                    2026,
                    1,
                    4,
                    tzinfo=UTC,
                ),
            ),
            (
                datetime(
                    2026,
                    1,
                    4,
                    tzinfo=UTC,
                ),
                datetime(
                    2026,
                    1,
                    7,
                    tzinfo=UTC,
                ),
            ),
            (
                datetime(
                    2026,
                    1,
                    7,
                    tzinfo=UTC,
                ),
                datetime(
                    2026,
                    1,
                    10,
                    tzinfo=UTC,
                ),
            ),
        ]

    def test_short_range_produces_one_window(self):
        short_end = datetime(
            2026,
            1,
            3,
            tzinfo=UTC,
        )

        windows = list(
            iter_date_windows(
                from_date=START,
                to_date=short_end,
                window_days=30,
            )
        )

        assert windows == [
            (
                START,
                short_end,
            )
        ]

    def test_equal_bounds_produce_no_windows(self):
        assert list(
            iter_date_windows(
                from_date=START,
                to_date=START,
                window_days=5,
            )
        ) == []

    def test_rejects_naive_datetime(self):
        with pytest.raises(
            ValueError,
            match="timezone-aware",
        ):
            list(
                iter_date_windows(
                    from_date=datetime(2026, 1, 1),
                    to_date=END,
                    window_days=5,
                )
            )

    def test_rejects_reversed_range(self):
        with pytest.raises(
            ValueError,
            match="from_date must be",
        ):
            list(
                iter_date_windows(
                    from_date=END,
                    to_date=START,
                    window_days=5,
                )
            )

    def test_rejects_invalid_window_size(self):
        with pytest.raises(
            ValueError,
            match="at least 1",
        ):
            list(
                iter_date_windows(
                    from_date=START,
                    to_date=END,
                    window_days=0,
                )
            )


def test_validate_historical_source_accepts_supported_source():
    validate_historical_source(
        source=make_source(),
        source_name="fake",
    )


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (
            make_source(update_mode="snapshot"),
            "does not support historical ingestion",
        ),
        (
            make_source(supports_backfill=False),
            "explicitly disables historical ingestion",
        ),
    ],
)
def test_validate_historical_source_rejects_unsupported_source(
    source,
    message,
):
    with pytest.raises(
        ValueError,
        match=message,
    ):
        validate_historical_source(
            source=source,
            source_name="fake",
        )


def test_historical_ingestion_aggregates_windows(
    monkeypatch: pytest.MonkeyPatch,
    storage,
    paths,
):
    results = iter(
        [
            make_ingestion_result(
                fetched=10,
                written=8,
                skipped=2,
            ),
            make_ingestion_result(
                fetched=20,
                written=15,
                skipped=5,
            ),
        ]
    )

    calls: list[dict[str, Any]] = []

    def fake_ingest_window(
        **kwargs: Any,
    ) -> IngestionResult:
        calls.append(kwargs)
        return next(results)

    monkeypatch.setattr(
        historical_module,
        "ingest_window",
        fake_ingest_window,
    )

    result = run_historical_ingestion(
        source=make_source(),
        source_name="fake",
        source_config={
            "ingestion": {},
        },
        storage=storage,
        paths=paths,
        from_date=START,
        to_date=END,
        window_days=5,
        seed_checkpoint=False,
    )

    assert result.status == "success"
    assert result.windows_total == 2
    assert result.windows_completed == 2
    assert result.records_fetched == 30
    assert result.records_written == 23
    assert result.records_skipped == 7
    assert result.error is None

    assert [
        (
            call["from_date"],
            call["to_date"],
        )
        for call in calls
    ] == [
        (
            datetime(
                2026,
                1,
                1,
                tzinfo=UTC,
            ),
            datetime(
                2026,
                1,
                6,
                tzinfo=UTC,
            ),
        ),
        (
            datetime(
                2026,
                1,
                6,
                tzinfo=UTC,
            ),
            datetime(
                2026,
                1,
                10,
                tzinfo=UTC,
            ),
        ),
    ]


def test_historical_ingestion_stops_after_failure(
    monkeypatch: pytest.MonkeyPatch,
    storage,
    paths,
):
    results = iter(
        [
            make_ingestion_result(
                fetched=10,
                written=8,
                skipped=2,
            ),
            make_ingestion_result(
                status="failure",
                error="API unavailable",
            ),
            make_ingestion_result(
                fetched=30,
                written=30,
            ),
        ]
    )

    calls: list[dict[str, Any]] = []

    def fake_ingest_window(
        **kwargs: Any,
    ) -> IngestionResult:
        calls.append(kwargs)
        return next(results)

    monkeypatch.setattr(
        historical_module,
        "ingest_window",
        fake_ingest_window,
    )

    result = run_historical_ingestion(
        source=make_source(),
        source_name="fake",
        source_config={
            "ingestion": {},
        },
        storage=storage,
        paths=paths,
        from_date=START,
        to_date=END,
        window_days=3,
        seed_checkpoint=False,
    )

    assert result.status == "failure"
    assert result.windows_total == 3
    assert result.windows_completed == 2
    assert result.records_fetched == 10
    assert result.records_written == 8
    assert result.records_skipped == 2
    assert result.error == "API unavailable"

    # The third window was not attempted.
    assert len(calls) == 2


def test_historical_ingestion_seeds_checkpoint(
    monkeypatch: pytest.MonkeyPatch,
    storage,
    paths,
):
    monkeypatch.setattr(
        historical_module,
        "ingest_window",
        lambda **kwargs: make_ingestion_result(
            fetched=10,
            written=10,
        ),
    )

    result = run_historical_ingestion(
        source=make_source(),
        source_name="fake",
        source_config={
            "ingestion": {},
        },
        storage=storage,
        paths=paths,
        from_date=START,
        to_date=END,
        window_days=5,
        seed_checkpoint=True,
    )

    assert result.status == "success"

    checkpoint = storage.read_checkpoint(
        paths.checkpoint_key("fake")
    )

    assert checkpoint == {
        "source": "fake",
        "last_successful_run_id": "backfill_seed",
        "last_checkpoint_value": END,
    }


def test_summarize_historical_ingestion():
    results = [
        make_ingestion_result(
            fetched=10,
            written=8,
            skipped=2,
        ),
        make_ingestion_result(
            fetched=20,
            written=15,
            skipped=5,
        ),
    ]

    summary = summarize_historical_ingestion(
        source_name="fake",
        from_date=START,
        to_date=END,
        window_days=5,
        windows_total=2,
        results=results,
        status="success",
    )

    assert summary.status == "success"
    assert summary.windows_total == 2
    assert summary.windows_completed == 2
    assert summary.records_fetched == 30
    assert summary.records_written == 23
    assert summary.records_skipped == 7
    assert summary.error is None