from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

import eml_transformer.standardization.pipeline as pipeline_module
from eml_transformer.schema.records import BronzeRecord
from eml_transformer.standardization.pipeline import (
    StandardizationPipeline,
    StandardizationResult,
)


UTC = timezone.utc

RETRIEVED_AT = datetime(
    2026,
    1,
    2,
    tzinfo=UTC,
)
PUBLISHED_AT = datetime(
    2026,
    1,
    1,
    tzinfo=UTC,
)


class FakeStandardizedRecord:
    def __init__(
        self,
        values: dict[str, Any],
    ) -> None:
        self.values = values

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return dict(self.values)


class FakeStandardizationSource:
    def __init__(
        self,
        *,
        name: str = "fake",
        results: list[Any] | None = None,
    ) -> None:
        self.name = name
        self.results = list(results or [])
        self.calls: list[BronzeRecord] = []

    def standardize_record(
        self,
        record: BronzeRecord,
    ) -> Any:
        self.calls.append(record)

        if not self.results:
            raise AssertionError(
                "No standardization result configured"
            )

        result = self.results.pop(0)

        if isinstance(result, Exception):
            raise result

        return result


def make_bronze_record(
    *,
    record_id: str = "record-1",
    source: str = "fake",
    text: str = "Test text",
) -> BronzeRecord:
    return BronzeRecord(
        source=source,
        record_id=record_id,
        published_at=PUBLISHED_AT,
        retrieved_at=RETRIEVED_AT,
        raw={
            "title": "Test title",
            "text": text,
        },
    )


def make_standardized_record(
    *,
    record_id: str = "record-1",
    source: str = "fake",
    text: str = "Test text",
) -> FakeStandardizedRecord:
    return FakeStandardizedRecord(
        {
            "record_id": record_id,
            "source": source,
            "source_type": "news",
            "title": "Test title",
            "text": text,
            "published_at": PUBLISHED_AT,
            "retrieved_at": RETRIEVED_AT,
            "url": None,
            "region": None,
            "categories": [],
            "dimensions": {},
            "metadata": {},
        }
    )


def test_run_source_standardizes_bronze_records(
    monkeypatch: pytest.MonkeyPatch,
    storage,
    paths,
):
    source = FakeStandardizationSource(
        results=[
            make_standardized_record(
                record_id="record-1",
            ),
            make_standardized_record(
                record_id="record-2",
            ),
        ]
    )

    create_calls: list[
        tuple[str, dict[str, Any]]
    ] = []

    def fake_create_source(
        source_name: str,
        **options: Any,
    ) -> FakeStandardizationSource:
        create_calls.append(
            (
                source_name,
                options,
            )
        )
        return source

    monkeypatch.setattr(
        pipeline_module,
        "create_source",
        fake_create_source,
    )

    bronze_key = paths.bronze_records(
        source="fake"
    )
    output_ref = "silver:fake:records"
    silver_key = paths.dataset(output_ref)

    storage.append_jsonl(
        bronze_key,
        [
            make_bronze_record(
                record_id="record-1",
            ).to_dict(),
            make_bronze_record(
                record_id="record-2",
            ).to_dict(),
        ],
    )

    pipeline = StandardizationPipeline(
        storage=storage,
        paths=paths,
    )

    result = pipeline.run_source(
        source_name="fake",
        source_config={
            "standardization": {
                "output": output_ref,
                "batch_size": 1,
                "write_mode": "replace",
                "options": {
                    "region": "MISO",
                },
            }
        },
    )

    assert result.status == "success"
    assert result.source == "fake"
    assert result.records_read == 2
    assert result.records_out == 2
    assert result.records_failed == 0
    assert result.bronze_key == bronze_key
    assert result.silver_key == silver_key
    assert result.error is None

    assert create_calls == [
        (
            "fake",
            {
                "region": "MISO",
            },
        )
    ]

    output = storage.read_dataset(output_ref)

    assert len(output) == 2
    assert output["record_id"].tolist() == [
        "record-1",
        "record-2",
    ]
    assert output["text"].tolist() == [
        "Test text",
        "Test text",
    ]


def test_run_source_skips_when_bronze_data_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    storage,
    paths,
):
    source = FakeStandardizationSource()

    monkeypatch.setattr(
        pipeline_module,
        "create_source",
        lambda *args, **kwargs: source,
    )

    pipeline = StandardizationPipeline(
        storage=storage,
        paths=paths,
    )

    result = pipeline.run_source(
        source_name="fake",
        source_config={
            "standardization": {
                "output": "silver:fake:records",
            }
        },
    )

    assert result.status == "skipped"
    assert result.source == "fake"
    assert result.records_read == 0
    assert result.records_out == 0
    assert result.records_failed == 0
    assert result.error == (
        "No bronze data found for source: fake"
    )

    assert storage.read_dataset(
        "silver:fake:records"
    ).empty


def test_run_source_supports_multiple_records_from_one_input(
    monkeypatch: pytest.MonkeyPatch,
    storage,
    paths,
):
    source = FakeStandardizationSource(
        results=[
            [
                make_standardized_record(
                    record_id="record-1-a",
                ),
                make_standardized_record(
                    record_id="record-1-b",
                ),
            ]
        ]
    )

    monkeypatch.setattr(
        pipeline_module,
        "create_source",
        lambda *args, **kwargs: source,
    )

    bronze_key = paths.bronze_records(
        source="fake"
    )

    storage.append_jsonl(
        bronze_key,
        [
            make_bronze_record().to_dict(),
        ],
    )

    pipeline = StandardizationPipeline(
        storage=storage,
        paths=paths,
    )

    result = pipeline.run_source(
        source_name="fake",
        source_config={
            "standardization": {
                "output": "silver:fake:records",
            }
        },
    )

    assert result.status == "success"
    assert result.records_read == 1
    assert result.records_out == 2
    assert result.records_failed == 0

    output = storage.read_dataset(
        "silver:fake:records"
    )

    assert output["record_id"].tolist() == [
        "record-1-a",
        "record-1-b",
    ]


def test_run_source_counts_failed_records_and_continues(
    monkeypatch: pytest.MonkeyPatch,
    storage,
    paths,
):
    source = FakeStandardizationSource(
        results=[
            ValueError("invalid source record"),
            make_standardized_record(
                record_id="record-2",
            ),
        ]
    )

    monkeypatch.setattr(
        pipeline_module,
        "create_source",
        lambda *args, **kwargs: source,
    )

    bronze_key = paths.bronze_records(
        source="fake"
    )

    storage.append_jsonl(
        bronze_key,
        [
            make_bronze_record(
                record_id="record-1",
            ).to_dict(),
            make_bronze_record(
                record_id="record-2",
            ).to_dict(),
        ],
    )

    pipeline = StandardizationPipeline(
        storage=storage,
        paths=paths,
    )

    result = pipeline.run_source(
        source_name="fake",
        source_config={
            "standardization": {
                "output": "silver:fake:records",
            }
        },
    )

    assert result.status == "success"
    assert result.records_read == 2
    assert result.records_out == 1
    assert result.records_failed == 1

    output = storage.read_dataset(
        "silver:fake:records"
    )

    assert len(output) == 1
    assert output.loc[0, "record_id"] == "record-2"


def test_run_source_ignores_none_results(
    monkeypatch: pytest.MonkeyPatch,
    storage,
    paths,
):
    source = FakeStandardizationSource(
        results=[
            None,
        ]
    )

    monkeypatch.setattr(
        pipeline_module,
        "create_source",
        lambda *args, **kwargs: source,
    )

    bronze_key = paths.bronze_records(
        source="fake"
    )

    storage.append_jsonl(
        bronze_key,
        [
            make_bronze_record().to_dict(),
        ],
    )

    pipeline = StandardizationPipeline(
        storage=storage,
        paths=paths,
    )

    result = pipeline.run_source(
        source_name="fake",
        source_config={
            "standardization": {
                "output": "silver:fake:records",
            }
        },
    )

    assert result.status == "success"
    assert result.records_read == 1
    assert result.records_out == 0
    assert result.records_failed == 0


def test_run_source_returns_failure_on_pipeline_error(
    monkeypatch: pytest.MonkeyPatch,
    storage,
    paths,
):
    def raise_creation_error(
        *args: Any,
        **kwargs: Any,
    ) -> None:
        raise RuntimeError(
            "Source creation failed"
        )

    monkeypatch.setattr(
        pipeline_module,
        "create_source",
        raise_creation_error,
    )

    pipeline = StandardizationPipeline(
        storage=storage,
        paths=paths,
    )

    result = pipeline.run_source(
        source_name="fake",
        source_config={
            "standardization": {},
        },
    )

    assert result.status == "failure"
    assert result.source == "fake"
    assert result.records_read == 0
    assert result.records_out == 0
    assert result.records_failed == 0
    assert result.error == "Source creation failed"


def test_source_options_prefers_nested_options():
    result = StandardizationPipeline._source_options(
        {
            "output": "silver:fake:records",
            "batch_size": 500,
            "write_mode": "replace",
            "options": {
                "region": "MISO",
                "office": "IND",
            },
        }
    )

    assert result == {
        "region": "MISO",
        "office": "IND",
    }


def test_source_options_supports_flat_configuration():
    result = StandardizationPipeline._source_options(
        {
            "output": "silver:fake:records",
            "batch_size": 500,
            "write_mode": "replace",
            "region": "MISO",
            "office": "IND",
        }
    )

    assert result == {
        "region": "MISO",
        "office": "IND",
    }


def test_result_summary():
    result = StandardizationResult(
        status="success",
        source="fake",
        records_read=10,
        records_out=8,
        records_failed=2,
        bronze_key="bronze-key",
        silver_key="silver-key",
    )

    assert result.to_summary() == {
        "source": "fake",
        "status": "success",
        "read": 10,
        "out": 8,
        "failed": 2,
        "bronze": "bronze-key",
        "silver": "silver-key",
        "error": None,
    }