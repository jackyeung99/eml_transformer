from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

import eml_transformer.ingestion.pipeline as pipeline_module
from eml_transformer.ingestion.pipeline import (
    IngestionPipeline,
)


def make_source_definition(
    *,
    name: str = "fake_source",
    ingestion_settings: dict[str, Any] | None = None,
) -> SimpleNamespace:
    """
    Minimal definition needed by IngestionPipeline.

    SourceDefinition itself should be tested separately. Using a small
    stand-in keeps these tests focused on pipeline behavior.
    """
    return SimpleNamespace(
        name=name,
        settings={
            "ingestion": (
                ingestion_settings
                if ingestion_settings is not None
                else {}
            ),
            "other_setting": "preserved",
        },
    )


def test_incremental_delegates_to_incremental_ingestion(
    monkeypatch: pytest.MonkeyPatch,
    storage,
    paths,
):
    definition = make_source_definition(
        ingestion_settings={
            "api_key": "test-key",
            "page_size": 100,
        }
    )
    to_date = datetime(
        2026,
        1,
        31,
        tzinfo=timezone.utc,
    )

    fake_source = object()
    expected_result = object()

    create_calls: list[
        tuple[str, dict[str, Any]]
    ] = []
    ingestion_calls: list[
        dict[str, Any]
    ] = []

    def fake_create_source(
        name: str,
        **settings: Any,
    ) -> object:
        create_calls.append(
            (
                name,
                settings,
            )
        )
        return fake_source

    def fake_run_incremental_ingestion(
        **kwargs: Any,
    ) -> object:
        ingestion_calls.append(kwargs)
        return expected_result

    monkeypatch.setattr(
        pipeline_module,
        "create_source",
        fake_create_source,
    )
    monkeypatch.setattr(
        pipeline_module,
        "run_incremental_ingestion",
        fake_run_incremental_ingestion,
    )

    pipeline = IngestionPipeline(
        storage=storage,
        paths=paths,
    )

    result = pipeline.incremental(
        definition,
        to_date=to_date,
    )

    assert result is expected_result

    assert create_calls == [
        (
            "fake_source",
            {
                "api_key": "test-key",
                "page_size": 100,
            },
        )
    ]

    assert ingestion_calls == [
        {
            "source": fake_source,
            "source_name": "fake_source",
            "source_config": definition.settings,
            "storage": storage,
            "paths": paths,
            "to_date": to_date,
        }
    ]


def test_incremental_uses_empty_ingestion_settings_by_default(
    monkeypatch: pytest.MonkeyPatch,
    storage,
    paths,
):
    definition = make_source_definition()
    fake_source = object()
    expected_result = object()

    create_calls: list[
        tuple[str, dict[str, Any]]
    ] = []

    def fake_create_source(
        name: str,
        **settings: Any,
    ) -> object:
        create_calls.append(
            (
                name,
                settings,
            )
        )
        return fake_source

    monkeypatch.setattr(
        pipeline_module,
        "create_source",
        fake_create_source,
    )
    monkeypatch.setattr(
        pipeline_module,
        "run_incremental_ingestion",
        lambda **kwargs: expected_result,
    )

    pipeline = IngestionPipeline(
        storage=storage,
        paths=paths,
    )

    result = pipeline.incremental(definition)

    assert result is expected_result
    assert create_calls == [
        (
            "fake_source",
            {},
        )
    ]


def test_incremental_returns_failure_when_dependency_raises(
    monkeypatch: pytest.MonkeyPatch,
    storage,
    paths,
):
    definition = make_source_definition()

    def raise_ingestion_error(
        **kwargs: Any,
    ) -> None:
        raise RuntimeError("simulated ingestion failure")

    monkeypatch.setattr(
        pipeline_module,
        "create_source",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        pipeline_module,
        "run_incremental_ingestion",
        raise_ingestion_error,
    )

    pipeline = IngestionPipeline(
        storage=storage,
        paths=paths,
    )

    result = pipeline.incremental(definition)

    assert result.status == "failure"
    assert result.source == "fake_source"
    assert result.reason == (
        "Incremental ingestion raised an exception"
    )
    assert result.error == (
        "simulated ingestion failure"
    )


def test_historical_delegates_to_historical_ingestion(
    monkeypatch: pytest.MonkeyPatch,
    storage,
    paths,
):
    definition = make_source_definition(
        ingestion_settings={
            "office": "IND",
        }
    )

    from_date = datetime(
        2025,
        1,
        1,
        tzinfo=timezone.utc,
    )
    to_date = datetime(
        2025,
        3,
        1,
        tzinfo=timezone.utc,
    )

    fake_source = object()
    expected_result = object()

    create_calls: list[
        tuple[str, dict[str, Any]]
    ] = []
    historical_calls: list[
        dict[str, Any]
    ] = []

    def fake_create_source(
        name: str,
        **settings: Any,
    ) -> object:
        create_calls.append(
            (
                name,
                settings,
            )
        )
        return fake_source

    def fake_run_historical_ingestion(
        **kwargs: Any,
    ) -> object:
        historical_calls.append(kwargs)
        return expected_result

    monkeypatch.setattr(
        pipeline_module,
        "create_source",
        fake_create_source,
    )
    monkeypatch.setattr(
        pipeline_module,
        "run_historical_ingestion",
        fake_run_historical_ingestion,
    )

    pipeline = IngestionPipeline(
        storage=storage,
        paths=paths,
    )

    result = pipeline.historical(
        definition,
        from_date=from_date,
        to_date=to_date,
        window_days=14,
        seed_checkpoint=True,
    )

    assert result is expected_result

    assert create_calls == [
        (
            "fake_source",
            {
                "office": "IND",
            },
        )
    ]

    assert historical_calls == [
        {
            "source": fake_source,
            "source_name": "fake_source",
            "source_config": definition.settings,
            "storage": storage,
            "paths": paths,
            "from_date": from_date,
            "to_date": to_date,
            "window_days": 14,
            "seed_checkpoint": True,
        }
    ]


def test_historical_returns_failure_when_dependency_raises(
    monkeypatch: pytest.MonkeyPatch,
    storage,
    paths,
):
    definition = make_source_definition()

    from_date = datetime(
        2025,
        1,
        1,
        tzinfo=timezone.utc,
    )
    to_date = datetime(
        2025,
        2,
        1,
        tzinfo=timezone.utc,
    )

    def raise_historical_error(
        **kwargs: Any,
    ) -> None:
        raise RuntimeError("simulated backfill failure")

    monkeypatch.setattr(
        pipeline_module,
        "create_source",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        pipeline_module,
        "run_historical_ingestion",
        raise_historical_error,
    )

    pipeline = IngestionPipeline(
        storage=storage,
        paths=paths,
    )

    result = pipeline.historical(
        definition,
        from_date=from_date,
        to_date=to_date,
        window_days=10,
        seed_checkpoint=False,
    )

    assert result.status == "failure"
    assert result.source == "fake_source"
    assert result.from_date == from_date
    assert result.to_date == to_date
    assert result.window_days == 10
    assert result.windows_total == 0
    assert result.windows_completed == 0
    assert result.records_fetched == 0
    assert result.records_written == 0
    assert result.records_skipped == 0
    assert result.records_failed == 0
    assert result.error == "simulated backfill failure"