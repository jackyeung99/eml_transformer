from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from eml_transformer.sources.text.gdelt import (
    GDELTSource,
)
from eml_transformer.sources.text.miso_notifications import (
    MISONotificationSource,
)
from eml_transformer.sources.text.newsapi import (
    NewsAPISource,
)
from eml_transformer.sources.text.weather_alerts import (
    WeatherAlertSource,
)
from eml_transformer.storage.paths import StoragePaths

from tests.fakes import (
    FakeEmbeddingModel,
    FakeForecastModel,
    FakeScraper,
    FakeSource,
    FakeStorage,
)


# =====================
# Runtime
# =====================

@pytest.fixture
def paths() -> StoragePaths:
    return StoragePaths()


@pytest.fixture
def storage(
    paths: StoragePaths,
) -> FakeStorage:
    return FakeStorage(paths=paths)


# =====================
# Test doubles
# =====================


@pytest.fixture
def fake_source_factory():
    def create(**overrides):
        return FakeSource(**overrides)

    return create


@pytest.fixture
def fake_source(
    fake_source_factory,
):
    return fake_source_factory()


@pytest.fixture
def fake_scraper(
    sample_scraped_article,
):
    return FakeScraper(
        result=sample_scraped_article
    )


@pytest.fixture
def failing_scraper():
    return FakeScraper(
        exc=RuntimeError("boom")
    )


@pytest.fixture
def embedding_model():
    return FakeEmbeddingModel()


@pytest.fixture
def forecast_model_factory():
    """
    Create independently configured fake forecast models.
    """
    def create(**overrides):
        return FakeForecastModel(**overrides)

    return create


@pytest.fixture
def forecast_model(
    forecast_model_factory,
):
    return forecast_model_factory()


# =====================
# Source configurations
# =====================

@pytest.fixture
def ingestion_config():
    return {
        "enabled": True,
        "ingestion": {
            "lookback_days": 1,
        },
    }


@pytest.fixture
def standardization_config():
    return {
        "enabled": True,
        "ingestion": {},
        "standardization": {
            "enabled": True,
            "output": "silver:gdelt:records",
            "batch_size": 100_000,
            "write_mode": "replace",
            "options": {},
        },
    }


@pytest.fixture
def scraping_config():
    return {
        "enabled": True,
        "ingestion": {},
        "scraping": {
            "enabled": True,
            "input": "silver:gdelt:records",
            "output": (
                "silver:gdelt:extracted_articles"
            ),
            "batch_size": 1,
            "write_mode": "replace",
            "retry_failed": True,
            "request_timeout": 1,
            "playwright_timeout": 1_000,
            "fallback_on_forbidden": False,
            "max_concurrency": 1,
        },
    }


@pytest.fixture
def embedding_config():
    return {
        "enabled": True,
        "ingestion": {},
        "embedding": {
            "enabled": True,
            "input": (
                "silver:gdelt:extracted_articles"
            ),
            "output": "gold:gdelt:embeddings",
            "write_mode": "append",
            "embedding_batch_size": 2,
            "text_columns": [
                "title",
                "text",
            ],
        },
    }

# =====================
# Source
# =====================


@pytest.fixture
def gdelt_source():
    return GDELTSource()


@pytest.fixture
def miso_source():
    return MISONotificationSource()


@pytest.fixture
def newsapi_source():
    return NewsAPISource(
        api_key="test-key",
        query="storm",
    )


@pytest.fixture
def weather_source():
    return WeatherAlertSource(
        areas=["IN"],
    )


