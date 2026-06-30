from datetime import date
import pytest
from eml_transformer.pipelines.backfill_pipeline import BackfillPipeline
from eml_transformer.pipelines.ingestion_pipeline import IngestionResult


def test_iter_date_windows():
    windows = list(
        BackfillPipeline._iter_date_windows(
            start=date.fromisoformat("2026-01-01"),
            end=date.fromisoformat("2026-01-10"),
            window_days=3,
        )
    )

    assert windows == [
        ("2026-01-01", "2026-01-03"),
        ("2026-01-04", "2026-01-06"),
        ("2026-01-07", "2026-01-09"),
        ("2026-01-10", "2026-01-10"),
    ]


def test_summarize_backfill(fake_ingestion_pipeline):
    pipeline = BackfillPipeline(
        ingestion_pipeline=fake_ingestion_pipeline(),
    )

    ingestion_results = [
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
            records_failed=1,
        ),
    ]

    result = pipeline._summarize_backfill(
        source_name="gdelt",
        start_date="2026-01-01",
        end_date="2026-01-10",
        window_days=5,
        windows_total=2,
        ingestion_results=ingestion_results,
        status="success",
    )

    assert result.status == "success"
    assert result.source == "gdelt"

    assert result.start_date == "2026-01-01"
    assert result.end_date == "2026-01-10"
    assert result.window_days == 5

    assert result.windows_total == 2
    assert result.windows_completed == 2

    assert result.records_fetched == 30
    assert result.records_written == 23
    assert result.records_skipped == 7
    assert result.records_failed == 1

    assert result.error is None

def test_summarize_backfill_failed(fake_ingestion_pipeline):
    pipeline = BackfillPipeline(
        ingestion_pipeline=fake_ingestion_pipeline(),
    )

    result = pipeline._summarize_backfill(
        source_name="gdelt",
        start_date="2026-01-01",
        end_date="2026-01-10",
        window_days=5,
        windows_total=0,
        ingestion_results=[],
        status="failed",
        error="Something went wrong",
    )

    assert result.status == "failed"
    assert result.records_fetched == 0
    assert result.records_written == 0
    assert result.records_skipped == 0
    assert result.records_failed == 0
    assert result.error == "Something went wrong"


def test_run_source_calls_ingestion_for_each_window(
    monkeypatch,
    fake_ingestion_pipeline,
    fake_source,
):
    monkeypatch.setattr(
        "eml_transformer.pipelines.backfill_pipeline.create_source",
        lambda source_name, **kwargs: fake_source(),
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
        source_config={"ingestion": {"foo": "bar"}},
        start_date="2026-01-01",
        end_date="2026-01-10",
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
            "source_config": {"ingestion": {"foo": "bar"}},
            "from_date": "2026-01-01",
            "to_date": "2026-01-05",
            "update_checkpoint": False,
        },
        {
            "source_name": "gdelt",
            "source_config": {"ingestion": {"foo": "bar"}},
            "from_date": "2026-01-06",
            "to_date": "2026-01-10",
            "update_checkpoint": False,
        },
    ]

def test_run_source_returns_failed_if_window_fails(
    monkeypatch,
    fake_ingestion_pipeline,
    fake_source,
):
    monkeypatch.setattr(
        "eml_transformer.pipelines.backfill_pipeline.create_source",
        lambda source_name, **kwargs: fake_source(),
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
                status="failed",
                source="gdelt",
                run_id="run-2",
                records_fetched=5,
                records_written=0,
                records_skipped=0,
                records_failed=5,
                error="download failed",
            ),
        ]
    )

    pipeline = BackfillPipeline(ingestion_pipeline)

    result = pipeline.run_source(
        source_name="gdelt",
        source_config={"ingestion": {}},
        start_date="2026-01-01",
        end_date="2026-01-10",
        window_days=5,
    )

    assert result.status == "failed"
    assert result.error == "download failed"
    assert result.windows_total == 2
    assert result.windows_completed == 2
    assert result.records_fetched == 15
    assert result.records_written == 10
    assert result.records_failed == 5


def test_run_source_seeds_checkpoint_after_success(
    monkeypatch,
    fake_ingestion_pipeline,
    fake_source,
):
    monkeypatch.setattr(
        "eml_transformer.pipelines.backfill_pipeline.create_source",
        lambda source_name, **kwargs: fake_source(),
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
        start_date="2026-01-01",
        end_date="2026-01-10",
        window_days=5,
        seed_checkpoint=True,
    )

    assert result.status == "success"

    assert ingestion_pipeline.checkpoints == [
        {
            "source_name": "gdelt",
            "checkpoint_value": "2026-01-10",
            "run_id": "backfill_seed",
        }
    ]

def test_run_source_does_not_seed_checkpoint_after_failure(
    monkeypatch,
    fake_ingestion_pipeline,
    fake_source,
):
    monkeypatch.setattr(
        "eml_transformer.pipelines.backfill_pipeline.create_source",
        lambda source_name, **kwargs: fake_source(),
    )

    ingestion_pipeline = fake_ingestion_pipeline(
        results=[
            IngestionResult(
                status="failed",
                source="gdelt",
                run_id="run-1",
                records_fetched=0,
                records_written=0,
                records_skipped=0,
                records_failed=1,
                error="failed",
            )
        ]
    )

    pipeline = BackfillPipeline(ingestion_pipeline)

    result = pipeline.run_source(
        source_name="gdelt",
        source_config={"ingestion": {}},
        start_date="2026-01-01",
        end_date="2026-01-05",
        window_days=5,
        seed_checkpoint=True,
    )

    assert result.status == "failed"
    assert ingestion_pipeline.checkpoints == []

def test_run_source_rejects_non_incremental_source(
    monkeypatch,
    fake_ingestion_pipeline,
    fake_source,
):
    monkeypatch.setattr(
        "eml_transformer.pipelines.backfill_pipeline.create_source",
        lambda source_name, **kwargs: fake_source(
            update_mode="snapshot",
            supports_backfill=True,
        ),
    )

    pipeline = BackfillPipeline(fake_ingestion_pipeline())

    with pytest.raises(ValueError, match="does not support backfill"):
        pipeline.run_source(
            source_name="gdelt",
            source_config={"ingestion": {}},
            start_date="2026-01-01",
            end_date="2026-01-05",
        )