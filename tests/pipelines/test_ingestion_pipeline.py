from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import Mock

import pytest

from eml_transformer.pipelines.ingestion_pipeline import (
    IngestionPipeline,
    IngestionResult,
)
from eml_transformer.utils.stamping import stable_hash

import logging

FIXED_TIME = datetime(
    2026,
    7,
    14,
    16,
    30,
    tzinfo=timezone.utc,
)


def make_record(
    record_id: str,
    published_at: Any = "2026-07-14T12:00:00Z",
) -> dict[str, Any]:
    return {
        "id": record_id,
        "text": f"Record {record_id}",
        "published_at": published_at,
    }


@pytest.fixture
def source_factory(fake_source):
    return Mock(return_value=fake_source)


@pytest.fixture
def pipeline(
    storage,
    paths,
    source_factory,
):
    return IngestionPipeline(
        storage=storage,
        paths=paths,
        source_factory=source_factory,
        clock=lambda: FIXED_TIME,
    )


class TestIngestionResult:
    def test_to_summary_contains_counts(self):
        result = IngestionResult(
            status="success",
            source="fake",
            run_id="run-1",
            records_fetched=3,
            records_written=2,
            records_skipped=1,
        )

        assert result.to_summary() == {
            "source": "fake",
            "status": "success",
            "run_id": "run-1",
            "fetched": 3,
            "written": 2,
            "skipped": 1,
            "failed": 0,
        }

    def test_to_summary_includes_error(self):
        result = IngestionResult(
            status="failed",
            source="fake",
            run_id="run-1",
            records_fetched=0,
            records_written=0,
            error="API failed",
        )

        assert result.to_summary()["error"] == "API failed"

    def test_to_summary_omits_error_when_none(self):
        result = IngestionResult(
            status="success",
            source="fake",
            run_id="run-1",
            records_fetched=0,
            records_written=0,
        )

        assert "error" not in result.to_summary()


class TestSourceFactory:
    def test_passes_only_ingestion_configuration(
        self,
        pipeline,
        source_factory,
    ):
        pipeline.run_source(
            source_name="fake",
            source_config={
                "ingestion": {
                    "timeout": 20,
                    "api_key": "test-key",
                },
                "standardization": {
                    "ignored": True,
                },
            },
        )

        source_factory.assert_called_once_with(
            "fake",
            timeout=20,
            api_key="test-key",
        )

    def test_missing_ingestion_config_passes_no_options(
        self,
        pipeline,
        source_factory,
    ):
        pipeline.run_source(
            source_name="fake",
            source_config={},
        )

        source_factory.assert_called_once_with("fake")

    def test_invalid_ingestion_config_returns_failure(
        self,
        pipeline,
        source_factory,
    ):
        result = pipeline.run_source(
            source_name="fake",
            source_config={
                "ingestion": ["not", "a", "mapping"],
            },
        )

        assert result.status == "failed"
        assert "must be a mapping" in result.error

        source_factory.assert_not_called()


class TestDateResolution:
    def test_explicit_from_date_overrides_checkpoint(
        self,
        pipeline,
        fake_source,
        storage,
        paths,
    ):
        checkpoint_key = paths.checkpoint_key(
            fake_source.name
        )

        storage.json_data[checkpoint_key] = {
            "last_checkpoint_value": (
                "2026-07-01T00:00:00+00:00"
            )
        }

        pipeline.run_source(
            source_name="fake",
            source_config={},
            from_date="2014-01-01",
            to_date="2014-01-31",
        )

        assert fake_source.fetch_calls == [
            {
                "from_date": "2014-01-01",
                "to_date": "2014-01-31",
            }
        ]

    def test_incremental_run_uses_checkpoint(
        self,
        pipeline,
        fake_source,
        storage,
        paths,
    ):
        checkpoint_key = paths.checkpoint_key(
            fake_source.name
        )

        storage.json_data[checkpoint_key] = {
            "last_checkpoint_value": (
                "2026-07-01T08:00:00-04:00"
            )
        }

        pipeline.run_source(
            source_name="fake",
            source_config={},
        )

        assert fake_source.fetch_calls == [
            {
                "from_date": (
                    "2026-07-01T12:00:00+00:00"
                ),
                "to_date": None,
            }
        ]

    def test_incremental_run_uses_default_lookback(
        self,
        pipeline,
        fake_source,
    ):
        fake_source.default_lookback_days = 7

        pipeline.run_source(
            source_name="fake",
            source_config={},
        )

        expected_date = (
            FIXED_TIME - timedelta(days=7)
        ).date().isoformat()

        assert fake_source.fetch_calls == [
            {
                "from_date": expected_date,
                "to_date": None,
            }
        ]

    def test_snapshot_source_does_not_use_checkpoint(
        self,
        pipeline,
        fake_source,
        storage,
        paths,
    ):
        fake_source.update_mode = "snapshot"

        storage.json_data[
            paths.checkpoint_key(fake_source.name)
        ] = {
            "last_checkpoint_value": (
                "2026-07-01T00:00:00+00:00"
            )
        }

        pipeline.run_source(
            source_name="fake",
            source_config={},
        )

        assert fake_source.fetch_calls == [
            {
                "from_date": None,
                "to_date": None,
            }
        ]

    def test_reversed_date_range_returns_failure(
        self,
        pipeline,
        fake_source,
    ):
        result = pipeline.run_source(
            source_name="fake",
            source_config={},
            from_date="2026-02-01",
            to_date="2026-01-01",
        )

        assert result.status == "failed"
        assert "from_date must not be after to_date" in (
            result.error
        )
        assert fake_source.fetch_calls == []


class TestBronzeConstruction:
    def test_writes_new_record_with_bronze_envelope(
        self,
        pipeline,
        fake_source,
        storage,
        paths,
    ):
        raw_record = make_record("one")

        fake_source.update_mode = "snapshot"
        fake_source.records = [raw_record]

        result = pipeline.run_source(
            source_name="fake",
            source_config={},
        )

        bronze_key = paths.bronze_records(
            fake_source.name
        )
        rows = storage.jsonl_data[bronze_key]

        assert result.status == "success"
        assert result.records_fetched == 1
        assert result.records_written == 1
        assert result.records_skipped == 0
        assert result.records_failed == 0

        assert len(rows) == 1

        assert rows[0] == {
            "source": fake_source.name,
            "run_id": pipeline._make_run_id(
                FIXED_TIME
            ),
            "retrieved_at": FIXED_TIME.isoformat(),
            "raw_record_hash": fake_source.unique_id(raw_record),
            "raw": raw_record,
        }

    def test_preserves_raw_record(
        self,
        pipeline,
        fake_source,
        storage,
        paths,
    ):
        raw_record = {
            "id": "one",
            "nested": {
                "values": [1, 2, 3],
            },
            "published_at": (
                "2026-07-14T12:00:00Z"
            ),
        }

        fake_source.update_mode = "snapshot"
        fake_source.records = [raw_record]

        pipeline.run_source("fake", {})

        bronze_key = paths.bronze_records(
            fake_source.name
        )

        assert (
            storage.jsonl_data[bronze_key][0][
                "raw"
            ]
            == raw_record
        )

    def test_empty_fetch_writes_nothing(
        self,
        pipeline,
        fake_source,
        storage,
        paths,
    ):
        fake_source.records = []

        result = pipeline.run_source(
            source_name="fake",
            source_config={},
        )

        assert result.status == "success"
        assert result.records_fetched == 0
        assert result.records_written == 0
        assert result.records_skipped == 0

        assert (
            paths.bronze_records(fake_source.name)
            not in storage.jsonl_data
        )
        assert (
            paths.dedupe_state(fake_source.name)
            not in storage.json_data
        )

    def test_malformed_record_returns_partial_success(
        self,
        pipeline,
        fake_source,
    ):
        fake_source.records = [
            make_record("valid"),
            "not-a-dictionary",
        ]

        result = pipeline.run_source(
            source_name="fake",
            source_config={},
            from_date="2014-01-01",
            to_date="2014-01-02",
        )

        assert result.status == "partial_success"
        assert result.records_fetched == 2
        assert result.records_written == 1
        assert result.records_skipped == 0
        assert result.records_failed == 1


class TestDeduplication:
    def test_duplicate_within_fetch_is_written_once(
        self,
        pipeline,
        fake_source,
        storage,
        paths,
    ):
        raw_record = make_record("one")

        fake_source.update_mode = "snapshot"
        fake_source.records = [
            raw_record,
            deepcopy(raw_record),
        ]

        result = pipeline.run_source(
            source_name="fake",
            source_config={},
        )

        bronze_key = paths.bronze_records(
            fake_source.name
        )

        assert result.records_fetched == 2
        assert result.records_written == 1
        assert result.records_skipped == 1

        assert len(
            storage.jsonl_data[bronze_key]
        ) == 1

    def test_previously_seen_record_is_skipped(
        self,
        pipeline,
        fake_source,
        storage,
        paths,
    ):
        raw_record = make_record("one")
        raw_hash = fake_source.unique_id(raw_record)

        fake_source.update_mode = "snapshot"
        fake_source.records = [raw_record]

        dedupe_key = paths.dedupe_state(
            fake_source.name
        )

        storage.json_data[dedupe_key] = {
            "seen": [raw_hash],
            "count": 1,
        }

        result = pipeline.run_source(
            source_name="fake",
            source_config={},
        )

        assert result.records_fetched == 1
        assert result.records_written == 0
        assert result.records_skipped == 1

        assert (
            paths.bronze_records(fake_source.name)
            not in storage.jsonl_data
        )

    def test_new_hashes_are_added_to_existing_state(
        self,
        pipeline,
        fake_source,
        storage,
        paths,
    ):
        old_record = make_record("old")
        new_record = make_record("new")

        old_hash = fake_source.unique_id(old_record)
        new_hash = fake_source.unique_id(new_record)

        fake_source.update_mode = "snapshot"
        fake_source.records = [old_record, new_record]

        dedupe_key = paths.dedupe_state(
            fake_source.name
        )

        storage.json_data[dedupe_key] = {
            "seen": [old_hash],
            "count": 1,
        }

        result = pipeline.run_source(
            source_name="fake",
            source_config={},
        )

        state = storage.json_data[dedupe_key]

        assert result.records_written == 1
        assert result.records_skipped == 1

        assert set(state["seen"]) == {
            old_hash,
            new_hash,
        }
        assert state["count"] == 2

    def test_repeated_backfill_is_idempotent(
        self,
        pipeline,
        fake_source,
        storage,
        paths,
    ):
        fake_source.records = [
            make_record("one"),
            make_record("two"),
        ]

        first_result = pipeline.run_source(
            source_name="fake",
            source_config={},
            from_date="2014-01-01",
            to_date="2014-01-31",
        )

        second_result = pipeline.run_source(
            source_name="fake",
            source_config={},
            from_date="2014-01-01",
            to_date="2014-01-31",
        )

        bronze_key = paths.bronze_records(
            fake_source.name
        )

        assert first_result.records_written == 2
        assert second_result.records_written == 0
        assert second_result.records_skipped == 2

        assert len(
            storage.jsonl_data[bronze_key]
        ) == 2

    def test_corrupt_dedupe_state_fails_safely(
        self,
        pipeline,
        fake_source,
        storage,
        paths,
    ):
        fake_source.records = [make_record("one")]

        dedupe_key = paths.dedupe_state(
            fake_source.name
        )

        storage.json_data[dedupe_key] = {
            "seen": "not-a-list",
        }

        result = pipeline.run_source(
            source_name="fake",
            source_config={},
        )

        assert result.status == "failed"
        assert "must be a list" in result.error

        assert (
            paths.bronze_records(fake_source.name)
            not in storage.jsonl_data
        )


class TestCheckpointBehavior:
    def test_incremental_run_saves_latest_checkpoint(
        self,
        pipeline,
        fake_source,
        storage,
        paths,
    ):
        fake_source.records = [
            make_record(
                "one",
                "2026-07-14T08:00:00-04:00",
            ),
            make_record(
                "two",
                "2026-07-14T14:00:00Z",
            ),
        ]

        result = pipeline.run_source(
            source_name="fake",
            source_config={},
        )

        checkpoint_key = paths.checkpoint_key(
            fake_source.name
        )
        checkpoint = storage.json_data[
            checkpoint_key
        ]

        assert result.status == "success"
        assert checkpoint["source"] == (
            fake_source.name
        )
        assert checkpoint[
            "last_successful_run_id"
        ] == result.run_id
        assert checkpoint[
            "last_checkpoint_value"
        ] == "2026-07-14T14:00:00+00:00"

    @pytest.mark.parametrize(
        ("from_date", "to_date"),
        [
            ("2014-01-01", "2014-01-31"),
            ("2014-01-01", None),
            (None, "2014-01-31"),
        ],
    )
    def test_bounded_run_does_not_update_checkpoint(
        self,
        pipeline,
        fake_source,
        storage,
        paths,
        from_date,
        to_date,
    ):
        fake_source.records = [
            make_record("one")
        ]

        pipeline.run_source(
            source_name="fake",
            source_config={},
            from_date=from_date,
            to_date=to_date,
        )

        checkpoint_key = paths.checkpoint_key(
            fake_source.name
        )

        assert (
            checkpoint_key
            not in storage.json_data
        )

    def test_update_checkpoint_false_prevents_update(
        self,
        pipeline,
        fake_source,
        storage,
        paths,
    ):
        fake_source.records = [
            make_record("one")
        ]

        pipeline.run_source(
            source_name="fake",
            source_config={},
            update_checkpoint=False,
        )

        assert (
            paths.checkpoint_key(fake_source.name)
            not in storage.json_data
        )

    def test_snapshot_source_does_not_update_checkpoint(
        self,
        pipeline,
        fake_source,
        storage,
        paths,
    ):
        fake_source.update_mode = "snapshot"
        fake_source.records = [
            make_record("one")
        ]

        pipeline.run_source(
            source_name="fake",
            source_config={},
        )

        assert (
            paths.checkpoint_key(fake_source.name)
            not in storage.json_data
        )

    def test_empty_fetch_does_not_update_checkpoint(
        self,
        pipeline,
        fake_source,
        storage,
        paths,
    ):
        fake_source.records = []

        pipeline.run_source(
            source_name="fake",
            source_config={},
        )

        assert (
            paths.checkpoint_key(fake_source.name)
            not in storage.json_data
        )

    def test_malformed_record_prevents_checkpoint_update(
        self,
        pipeline,
        fake_source,
        storage,
        paths,
    ):
        fake_source.records = [
            make_record("valid"),
            "not-a-dictionary",
        ]

        result = pipeline.run_source(
            source_name="fake",
            source_config={},
        )

        assert result.status == "partial_success"

        assert (
            paths.checkpoint_key(fake_source.name)
            not in storage.json_data
        )

    def test_invalid_checkpoint_value_is_skipped(
        self,
        pipeline,
        fake_source,
        storage,
        paths,
        caplog,
    ):
        fake_source.records = [
            make_record("bad", 123),
            make_record(
                "good",
                "2026-07-14T15:00:00Z",
            ),
        ]

        with caplog.at_level(logging.WARNING):
            pipeline.run_source(
                source_name="fake",
                source_config={},
            )

        checkpoint = storage.json_data[
            paths.checkpoint_key(
                fake_source.name
            )
        ]

        assert checkpoint[
            "last_checkpoint_value"
        ] == "2026-07-14T15:00:00+00:00"

        assert (
            "Skipping malformed checkpoint value"
            in caplog.text
        )

    def test_no_valid_checkpoint_does_not_write_checkpoint(
        self,
        pipeline,
        fake_source,
        storage,
        paths,
    ):
        fake_source.records = [
            make_record("one", None),
            make_record("two", None),
        ]

        result = pipeline.run_source(
            source_name="fake",
            source_config={},
        )

        assert result.status == "success"
        assert (
            paths.checkpoint_key(fake_source.name)
            not in storage.json_data
        )

    def test_initialize_checkpoint_normalizes_to_utc(
        self,
        pipeline,
        fake_source,
        storage,
        paths,
    ):
        pipeline.initialize_checkpoint(
            source_name=fake_source.name,
            checkpoint_value=(
                "2026-07-14T08:00:00-04:00"
            ),
        )

        checkpoint = storage.json_data[
            paths.checkpoint_key(
                fake_source.name
            )
        ]

        assert checkpoint[
            "last_checkpoint_value"
        ] == "2026-07-14T12:00:00+00:00"

        assert checkpoint[
            "last_successful_run_id"
        ] == "manual_init"

    def test_initialize_checkpoint_rejects_naive_time(
        self,
        pipeline,
        fake_source,
    ):
        with pytest.raises(
            ValueError,
            match="timezone-aware",
        ):
            pipeline.initialize_checkpoint(
                source_name=fake_source.name,
                checkpoint_value=(
                    "2026-07-14T12:00:00"
                ),
            )


class TestFailureOrdering:
    def test_fetch_failure_writes_no_state(
        self,
        pipeline,
        fake_source,
        storage,
    ):
        fake_source.fetch_error = RuntimeError(
            "API unavailable"
        )

        result = pipeline.run_source(
            source_name="fake",
            source_config={},
        )

        assert result.status == "failed"
        assert result.error == "API unavailable"
        assert result.records_fetched == 0

        assert storage.jsonl_data == {}
        assert storage.json_data == {}

    def test_bronze_failure_does_not_save_state(
        self,
        pipeline,
        fake_source,
        storage,
        paths,
    ):
        fake_source.records = [
            make_record("one")
        ]

        bronze_key = paths.bronze_records(
            fake_source.name
        )

        storage.append_errors[bronze_key] = (
            RuntimeError("bronze write failed")
        )

        result = pipeline.run_source(
            source_name="fake",
            source_config={},
        )

        assert result.status == "failed"
        assert result.records_fetched == 1
        assert result.records_written == 0

        assert (
            paths.dedupe_state(fake_source.name)
            not in storage.json_data
        )
        assert (
            paths.checkpoint_key(fake_source.name)
            not in storage.json_data
        )

    def test_dedupe_failure_does_not_update_checkpoint(
        self,
        pipeline,
        fake_source,
        storage,
        paths,
    ):
        fake_source.records = [
            make_record("one")
        ]

        dedupe_key = paths.dedupe_state(
            fake_source.name
        )

        storage.write_errors[dedupe_key] = (
            RuntimeError("dedupe write failed")
        )

        result = pipeline.run_source(
            source_name="fake",
            source_config={},
        )

        assert result.status == "failed"
        assert result.records_fetched == 1
        assert result.records_written == 1

        assert (
            paths.checkpoint_key(fake_source.name)
            not in storage.json_data
        )

    def test_checkpoint_failure_returns_failed_result(
        self,
        pipeline,
        fake_source,
        storage,
        paths,
    ):
        fake_source.records = [
            make_record("one")
        ]

        checkpoint_key = paths.checkpoint_key(
            fake_source.name
        )

        storage.write_errors[checkpoint_key] = (
            RuntimeError("checkpoint write failed")
        )

        result = pipeline.run_source(
            source_name="fake",
            source_config={},
        )

        assert result.status == "failed"
        assert result.records_written == 1
        assert "checkpoint write failed" in (
            result.error
        )

        # Dedupe state completed before checkpoint failure.
        assert (
            paths.dedupe_state(fake_source.name)
            in storage.json_data
        )


class TestSourceValidation:
    @pytest.mark.parametrize(
        ("update_mode", "lookback", "error"),
        [
            (
                "unsupported",
                7,
                "Unsupported update mode",
            ),
            (
                "incremental",
                -1,
                "must not be negative",
            ),
            (
                "incremental",
                "seven",
                "must be an integer",
            ),
        ],
    )
    def test_invalid_source_configuration(
        self,
        pipeline,
        fake_source,
        update_mode,
        lookback,
        error,
    ):
        fake_source.update_mode = update_mode
        fake_source.default_lookback_days = lookback

        result = pipeline.run_source(
            source_name="fake",
            source_config={},
        )

        assert result.status == "failed"
        assert error in result.error
        assert fake_source.fetch_calls == []


class TestRunAll:
    def test_runs_all_sources_and_isolates_failure(
        self,
        storage,
        paths,
    ):
        good_source = Mock()
        good_source.name = "good"
        good_source.update_mode = "snapshot"
        good_source.default_lookback_days = 7
        good_source.fetch_records.return_value = []
        good_source.get_checkpoint_value.return_value = None

        bad_source = Mock()
        bad_source.name = "bad"
        bad_source.update_mode = "snapshot"
        bad_source.default_lookback_days = 7
        bad_source.fetch_records.side_effect = (
            RuntimeError("source failed")
        )
        bad_source.get_checkpoint_value.return_value = None

        def source_factory(
            source_name: str,
            **_: Any,
        ):
            return {
                "good": good_source,
                "bad": bad_source,
            }[source_name]

        pipeline = IngestionPipeline(
            storage=storage,
            paths=paths,
            source_factory=source_factory,
            clock=lambda: FIXED_TIME,
        )

        results = pipeline.run_all(
            {
                "good": {},
                "bad": {},
            }
        )

        assert [
            result.source for result in results
        ] == ["good", "bad"]

        assert [
            result.status for result in results
        ] == ["success", "failed"]