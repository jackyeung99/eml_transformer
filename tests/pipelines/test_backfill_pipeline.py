from datetime import date
import pytest
from eml_transformer.pipelines.backfill_pipeline import BackfillPipeline
from eml_transformer.pipelines.ingestion_pipeline import IngestionResult
from eml_transformer.pipelines.backfill_pipeline import BackfillResult

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

def test_iter_date_windows_single_day():
    windows = list(
        BackfillPipeline._iter_date_windows(
            start=date.fromisoformat("2026-01-01"),
            end=date.fromisoformat("2026-01-01"),
            window_days=5
        )
    )
    assert windows == [("2026-01-01", "2026-01-01")]

def test_iter_date_windows_exact_multiple():
    windows = list(
        BackfillPipeline._iter_date_windows(
            start=date.fromisoformat("2026-01-01"),
            end=date.fromisoformat("2026-01-06"),
            window_days=3
        )
    )
    assert windows == [
        ("2026-01-01", "2026-01-03"),
        ("2026-01-04", "2026-01-06")
    ]

def test_iter_date_windows_range_smaller_than_window():
    windows = list(
        BackfillPipeline._iter_date_windows(
            start=date.fromisoformat("2026-01-01"),
            end=date.fromisoformat("2026-01-03"),
            window_days=30
        )
    )
    assert windows == [("2026-01-01", "2026-01-03")]

def test_iter_date_windows_window_size_of_one():
    windows = list(
        BackfillPipeline._iter_date_windows(
            start=date.fromisoformat("2026-01-01"),
            end=date.fromisoformat("2026-01-03"),
            window_days=1
        )
    )
    assert windows == [
        ("2026-01-01", "2026-01-01"),
        ("2026-01-02", "2026-01-02"),
        ("2026-01-03", "2026-01-03")
    ]

def test_to_summary_returns_expected_keys():
    result = BackfillResult(
        status="success",
        source="gdelt",
        start_date="2026-01-01",
        end_date="2026-01-10",
        window_days=5,
        windows_total=2,
        windows_completed=2,
        records_fetched=30,
        records_written=23,
        records_skipped=7
    )
    summary = result.to_summary()
    expected_keys = {"source", "status", "start", "end", "windows", "fetched", "written", "skipped", "failed"}
    assert set(summary.keys()) == expected_keys

def test_to_summary_windows_formatted_as_completed_over_total():
    result = BackfillResult(
        status="success",
        source="gdelt",
        start_date="2026-01-01",
        end_date="2026-01-10",
        window_days=5,
        windows_total=3,
        windows_completed=2,
        records_fetched=0,
        records_written=0,
        records_skipped=0
    )
    assert result.to_summary()["windows"] == "2/3"

def test_to_summary_includes_error_when_present():
    result = BackfillResult(
        status="failed",
        source="gdelt",
        start_date="2026-01-01",
        end_date="2026-01-10",
        window_days=5,
        windows_total=2,
        windows_completed=1,
        records_fetched=0,
        records_written=0,
        records_skipped=0,
        error="Connection timeout"
    )
    summary = result.to_summary()
    assert summary["error"] == "Connection timeout"

def test_to_summary_omits_error_when_none():
    result = BackfillResult(
        status="success",
        source="gdelt",
        start_date="2026-01-01",
        end_date="2026-01-10",
        window_days=5,
        windows_total=2,
        windows_completed=2,
        records_fetched=10,
        records_written=10,
        records_skipped=0
    )
    assert "error" not in result.to_summary()
    
    

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
        lambda source_name, **kwargs: fake_source,
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

# def test_run_source_rejects_non_incremental_source(
#     monkeypatch,
#     fake_ingestion_pipeline,
#     fake_source_factory,
# ):
    
#     source = fake_source_factory(
#         update_mode="snapshot",
#         supports_backfill=False,
#     )


#     monkeypatch.setattr(
#         "eml_transformer.pipelines.backfill_pipeline.create_source",
#         lambda source_name, **kwargs: source
#     )

#     pipeline = BackfillPipeline(fake_ingestion_pipeline())

#     with pytest.raises(ValueError, match="does not support backfill"):
#         pipeline.run_source(
#             source_name="gdelt",
#             source_config={"ingestion": {}},
#             start_date="2026-01-01",
#             end_date="2026-01-05",
#         )

# def test_run_source_rejects_when_supports_backfill_is_false(
#         monkeypatch,
#         fake_ingestion_pipeline,
#         fake_source_factory
# ):  
    
#     source = fake_source_factory(
#         update_mode="snapshot",
#         supports_backfill=True,
#     )

#     monkeypatch.setattr(
#         "eml_transformer.pipelines.backfill_pipeline.create_source",
#         lambda source_name, **kwargs: source
#     )

#     pipeline = BackfillPipeline(fake_ingestion_pipeline())

#     with pytest.raises(ValueError, match="explicitly disables backfill"):
#         pipeline.run_source(
#             source_name="gdelt",
#             source_config={"ingestion": {}},
#             start_date="2026-01-01",
#             end_date="2026-01-05"
#         )

def test_run_source_does_not_seed_checkpoint_by_default(
        monkeypatch,
        fake_ingestion_pipeline,
        fake_source
):
    """seed_checkpoint defaults to False"""
    monkeypatch.setattr(
        "eml_transformer.pipelines.backfill_pipeline.create_source",
        lambda source_name, **kwargs: fake_source
    )

    ingestion_pipeline = fake_ingestion_pipeline(
        results=[
            IngestionResult(
                status="success", source="gdelt", run_id="run-1",
                records_fetched=10, records_written=10, records_skipped=0
            )
        ]
    )

    pipeline = BackfillPipeline(ingestion_pipeline)
    pipeline.run_source(
        source_name="gdelt",
        source_config={"ingestion": {}},
        start_date="2026-01-01",
        end_date="2026-01-05"
    )

    assert ingestion_pipeline.checkpoints == []

def test_run_source_uses_default_window_days_of_20(
        monkeypatch,
        fake_ingestion_pipeline,
        fake_source
):
    """window_days defaults to 30"""
    monkeypatch.setattr(
        "eml_transformer.pipelines.backfill_pipeline.create_source",
        lambda source_name, **kwargs: fake_source
    )

    ingestion_pipeline = fake_ingestion_pipeline(
        results=[
            IngestionResult(
                status="success", source="gdelt", run_id="run-1",
                records_fetched=1, records_written=1, records_skipped=0
            )
        ]
    )

    pipeline = BackfillPipeline(ingestion_pipeline)
    result = pipeline.run_source(
        source_name="gdelt",
        source_config={"ingestion": {}},
        start_date="2026-01-01",
        end_date="2026-01-15"
    )

    assert result.window_days == 30
    assert result.windows_total == 1

def test_run_source_uses_last_window_end_for_checkpoint(
    monkeypatch,
    fake_ingestion_pipeline,
    fake_source,
):
    """Checkpoint seed should be the end date of the final window, not the requested end_date."""
    monkeypatch.setattr(
        "eml_transformer.pipelines.backfill_pipeline.create_source",
        lambda source_name, **kwargs: fake_source,
    )

    ingestion_pipeline = fake_ingestion_pipeline(
        results=[
            IngestionResult(
                status="success", source="gdelt", run_id="run-1",
                records_fetched=1, records_written=1, records_skipped=0,
            ),
            IngestionResult(
                status="success", source="gdelt", run_id="run-2",
                records_fetched=1, records_written=1, records_skipped=0,
            ),
        ]
    )

    pipeline = BackfillPipeline(ingestion_pipeline)
    pipeline.run_source(
        source_name="gdelt",
        source_config={"ingestion": {}},
        start_date="2026-01-01",
        end_date="2026-01-10",
        window_days=5,
        seed_checkpoint=True,
    )

    assert ingestion_pipeline.checkpoints[0]["checkpoint_value"] == "2026-01-10"


class TestRunAll:
    """Test the run_all method."""

    def test_returns_empty_dict_for_empty_configs(
        self,
        monkeypatch,
        fake_ingestion_pipeline,
        fake_source,
    ):
        monkeypatch.setattr(
            "eml_transformer.pipelines.backfill_pipeline.create_source",
            lambda source_name, **kwargs: fake_source,
        )

        pipeline = BackfillPipeline(fake_ingestion_pipeline())
        results = pipeline.run_all(
            source_configs={},
            start_date="2026-01-01",
            end_date="2026-01-10",
        )
        assert results == []

    def test_calls_run_source_for_each_config(
        self,
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
                    status="success", source="gdelt", run_id="run-1",
                    records_fetched=10, records_written=10, records_skipped=0,
                ),
                IngestionResult(
                    status="success", source="newsapi", run_id="run-2",
                    records_fetched=5, records_written=5, records_skipped=0,
                ),
            ]
        )

        pipeline = BackfillPipeline(ingestion_pipeline)
        results = pipeline.run_all(
            source_configs={
                "gdelt": {"ingestion": {}},
                "newsapi": {"ingestion": {}},
            },
            start_date="2026-01-01",
            end_date="2026-01-30",
        )

        assert len(results) == 2
        assert results[0].source == 'gdelt'
        assert results[1].source == 'newsapi'

    def test_skips_sources_that_do_not_support_backfill(
        self,
        monkeypatch,
        fake_ingestion_pipeline,
        fake_source_factory,
    ):
        def create_source_mock(source_name, **kwargs):
            if source_name == "weather_alerts":
                return fake_source_factory(supports_backfill=False)

            return fake_source_factory()

        monkeypatch.setattr(
            "eml_transformer.pipelines.backfill_pipeline.create_source",
            create_source_mock,
        )

        ingestion_pipeline = fake_ingestion_pipeline(
            results=[
                IngestionResult(
                    status="success",
                    source="gdelt",
                    run_id="run-1",
                    records_fetched=1,
                    records_written=1,
                    records_skipped=0,
                ),
            ]
        )

        pipeline = BackfillPipeline(ingestion_pipeline)

        results = pipeline.run_all(
            source_configs={
                "gdelt": {"ingestion": {}},
                "weather_alerts": {"ingestion": {}},
            },
            start_date="2026-01-01",
            end_date="2026-01-30",
        )

        assert len(results) == 1
        assert "gdelt" == results[0].source

    def test_returns_backfill_result_for_each_source(
        self,
        monkeypatch,
        fake_ingestion_pipeline,
        fake_source,
    ):
        from eml_transformer.pipelines.backfill_pipeline import BackfillResult

        monkeypatch.setattr(
            "eml_transformer.pipelines.backfill_pipeline.create_source",
            lambda source_name, **kwargs: fake_source,
        )

        ingestion_pipeline = fake_ingestion_pipeline(
            results=[
                IngestionResult(
                    status="success", source="gdelt", run_id="run-1",
                    records_fetched=10, records_written=10, records_skipped=0,
                ),
            ]
        )

        pipeline = BackfillPipeline(ingestion_pipeline)
        results = pipeline.run_all(
            source_configs={"gdelt": {"ingestion": {}}},
            start_date="2026-01-01",
            end_date="2026-01-30",
        )
        
        assert results[0].source == "gdelt"

    def test_passes_dates_and_window_days_through(
        self,
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
                    status="success", source="gdelt", run_id="run-1",
                    records_fetched=1, records_written=1, records_skipped=0,
                ),
                IngestionResult(
                    status="success", source="gdelt", run_id="run-2",
                    records_fetched=1, records_written=1, records_skipped=0,
                ),
            ]
        )

        pipeline = BackfillPipeline(ingestion_pipeline)
        results = pipeline.run_all(
            source_configs={"gdelt": {"ingestion": {}}},
            start_date="2026-01-01",
            end_date="2026-01-10",
            window_days=5,
        )

        assert results[0].start_date == "2026-01-01"
        assert results[0].end_date == "2026-01-10"
        assert results[0].window_days == 5
        assert results[0].windows_total == 2

    def test_continues_processing_after_failed_source(
        self,
        monkeypatch,
        fake_ingestion_pipeline,
        fake_source,
    ):
        """A failed source shouldn't stop other sources from running."""
        monkeypatch.setattr(
            "eml_transformer.pipelines.backfill_pipeline.create_source",
            lambda source_name, **kwargs: fake_source,
        )

        ingestion_pipeline = fake_ingestion_pipeline(
            results=[
                IngestionResult(
                    status="failed", source="gdelt", run_id="run-1",
                    records_fetched=0, records_written=0, records_skipped=0,
                    records_failed=1, error="download failed",
                ),
                IngestionResult(
                    status="success", source="newsapi", run_id="run-2",
                    records_fetched=5, records_written=5, records_skipped=0,
                ),
            ]
        )

        pipeline = BackfillPipeline(ingestion_pipeline)
        results = pipeline.run_all(
            source_configs={
                "gdelt": {"ingestion": {}},
                "newsapi": {"ingestion": {}},
            },
            start_date="2026-01-01",
            end_date="2026-01-30",
        )

        assert results[0].status == "failed"
        assert results[1].status == "success"