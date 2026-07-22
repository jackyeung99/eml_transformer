from datetime import datetime, timedelta, timezone

import pytest

from eml_transformer.pipelines.backfill_pipeline import (
    BackfillPipeline,
    BackfillResult,
)
from eml_transformer.pipelines.ingestion_pipeline import (
    IngestionResult,
)


UTC = timezone.utc

START = datetime(2026, 1, 1, tzinfo=UTC)
END = datetime(2026, 1, 10, tzinfo=UTC)


class TestDateWindows:
    def test_splits_range_into_windows(self):
        windows = list(
            BackfillPipeline._iter_date_windows(
                from_date=START,
                to_date=END,
                window_days=3,
            )
        )

        assert windows == [
            (
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 1, 4, tzinfo=UTC),
            ),
            (
                datetime(2026, 1, 4, tzinfo=UTC),
                datetime(2026, 1, 7, tzinfo=UTC),
            ),
            (
                datetime(2026, 1, 7, tzinfo=UTC),
                datetime(2026, 1, 10, tzinfo=UTC),
            ),
        ]

    def test_range_smaller_than_window(self):
        end = datetime(2026, 1, 3, tzinfo=UTC)

        windows = list(
            BackfillPipeline._iter_date_windows(
                from_date=START,
                to_date=end,
                window_days=30,
            )
        )

        assert windows == [(START, end)]

    def test_window_size_of_one_day(self):
        end = datetime(2026, 1, 4, tzinfo=UTC)

        windows = list(
            BackfillPipeline._iter_date_windows(
                from_date=START,
                to_date=end,
                window_days=1,
            )
        )

        assert windows == [
            (
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 1, 2, tzinfo=UTC),
            ),
            (
                datetime(2026, 1, 2, tzinfo=UTC),
                datetime(2026, 1, 3, tzinfo=UTC),
            ),
            (
                datetime(2026, 1, 3, tzinfo=UTC),
                datetime(2026, 1, 4, tzinfo=UTC),
            ),
        ]

    def test_equal_bounds_produce_no_windows(self):
        windows = list(
            BackfillPipeline._iter_date_windows(
                from_date=START,
                to_date=START,
                window_days=5,
            )
        )

        assert windows == []

    def test_rejects_naive_datetime(self):
        with pytest.raises(
            ValueError,
            match="timezone-aware",
        ):
            list(
                BackfillPipeline._iter_date_windows(
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
                BackfillPipeline._iter_date_windows(
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
                BackfillPipeline._iter_date_windows(
                    from_date=START,
                    to_date=END,
                    window_days=0,
                )
            )


def test_run_source_calls_ingestion_for_each_window(
    monkeypatch,
    fake_ingestion_pipeline,
    fake_source,
):
    monkeypatch.setattr(
        "eml_transformer.pipelines.backfill_pipeline.create_source",
        lambda source_name, **kwargs: fake_source,
    )

    ingestion_pipeline = fake_ingestion_pipeline(
        results=[
            IngestionResult(
                status="success",
                source="gdelt",
                run_id="run-1",
                records_fetched=10,
                records_written=8,
                records_skipped=2,
            ),
            IngestionResult(
                status="success",
                source="gdelt",
                run_id="run-2",
                records_fetched=20,
                records_written=15,
                records_skipped=5,
            ),
        ]
    )

    pipeline = BackfillPipeline(ingestion_pipeline)

    result = pipeline.run_source(
        source_name="gdelt",
        source_config={
            "ingestion": {"foo": "bar"}
        },
        from_date=START,
        to_date=END,
        window_days=5,
    )

    assert result.status == "success"
    assert result.windows_total == 2
    assert result.windows_completed == 2
    assert result.records_fetched == 30
    assert result.records_written == 23
    assert result.records_skipped == 7

    assert ingestion_pipeline.calls == [
        {
            "source_name": "gdelt",
            "source_config": {
                "ingestion": {"foo": "bar"}
            },
            "from_date": datetime(
                2026, 1, 1, tzinfo=UTC
            ),
            "to_date": datetime(
                2026, 1, 6, tzinfo=UTC
            ),
            "update_checkpoint": False,
        },
        {
            "source_name": "gdelt",
            "source_config": {
                "ingestion": {"foo": "bar"}
            },
            "from_date": datetime(
                2026, 1, 6, tzinfo=UTC
            ),
            "to_date": datetime(
                2026, 1, 10, tzinfo=UTC
            ),
            "update_checkpoint": False,
        },
    ]


def test_run_source_seeds_checkpoint_after_success(
    monkeypatch,
    fake_ingestion_pipeline,
    fake_source,
):
    monkeypatch.setattr(
        "eml_transformer.pipelines.backfill_pipeline.create_source",
        lambda source_name, **kwargs: fake_source,
    )

    ingestion_pipeline = fake_ingestion_pipeline(
        results=[
            IngestionResult(
                status="success",
                source="gdelt",
                run_id="run-1",
                records_fetched=10,
                records_written=10,
                records_skipped=0,
            ),
            IngestionResult(
                status="success",
                source="gdelt",
                run_id="run-2",
                records_fetched=20,
                records_written=20,
                records_skipped=0,
            ),
        ]
    )

    pipeline = BackfillPipeline(ingestion_pipeline)

    result = pipeline.run_source(
        source_name="gdelt",
        source_config={"ingestion": {}},
        from_date=START,
        to_date=END,
        window_days=5,
        seed_checkpoint=True,
    )

    assert result.status == "success"

    assert ingestion_pipeline.checkpoints == [
        {
            "source_name": "gdelt",
            "checkpoint": {
                "source": "gdelt",
                "last_successful_run_id": "backfill_seed",
                "last_checkpoint_value": END,
            },
        }
    ]