from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import pytest

from eml_transformer.storage.paths import StoragePaths
from tests.helpers import FakeEmbeddingModel, FakeScraper, FakeSource, FakeStorage, FakeIngestionPipeline
from eml_transformer.ingestion.sources.gdelt import GDELTSource
from eml_transformer.ingestion.sources.miso import MISONotificationSource

# run time 
@pytest.fixture
def storage():
    return FakeStorage()


@pytest.fixture
def paths():
    return StoragePaths()


# dependency injection helper 
@pytest.fixture
def fake_ingestion_pipeline():
    return FakeIngestionPipeline


@pytest.fixture
def fake_source():
    return FakeSource

@pytest.fixture
def fake_scraper(sample_scraped_article):
    return FakeScraper(result=sample_scraped_article)


@pytest.fixture
def failing_scraper():
    return FakeScraper(exc=RuntimeError("boom"))


@pytest.fixture
def embedding_model():
    return FakeEmbeddingModel()


@pytest.fixture
def gdelt_source():
    return GDELTSource()

# configs 
@pytest.fixture
def ingestion_config():
    return {
        "enabled": True,
        "ingestion": {},
    }


@pytest.fixture
def standardization_config():
    return {
        "enabled": True,
        "ingestion": {},
        "standardization": {
            "enabled": True,
            "input": "raw_records",
            "output": "records",
        },
    }


@pytest.fixture
def scraping_config():
    return {
        "enabled": True,
        "ingestion": {},
        "scraping": {
            "enabled": True,
            "input": "records",
            "output": "extracted_articles",
            "batch_size": 1,
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
            "input": "extracted_articles",
            "output": "embeddings",
            "text_columns": ["title", "text"],
            "batch_size": 2,
            "model_name": "fake-model",
        },
    }


@pytest.fixture
def sample_raw_records():
    return pd.DataFrame(
        [
            {
                "record_id": "gdelt-1",
                "url": "https://example.com/article",
                "title": "Raw storm title",
                "text": "Raw article text.",
                "published_at": "2026-06-24T12:00:00Z",
                "metadata": {"raw": True},
            }
        ]
    )


@pytest.fixture
def sample_standardized_records():
    return pd.DataFrame(
        [
            {
                "record_id": "gdelt-1",
                "source": "gdelt",
                "source_type": "news",
                "url": "https://example.com/article",
                "published_at": "2026-06-24T12:00:00Z",
                "retrieved_at": "2026-06-24T13:00:00Z",
                "title": "Storm title",
                "text": "Storm article text.",
                "region": None,
                "categories": ["news", "gdelt"],
                "metadata": {},
                "raw": {},
            }
        ]
    )


@pytest.fixture
def sample_scraped_article():
    return {
        "success": True,
        "scrape_status": "success",
        "title": "Storm causes outage",
        "text": "Thousands lost power.",
        "published_at": "2026-06-24T12:30:00Z",
        "metadata": {
            "method": "trafilatura",
            "published_at_source": "json_ld",
        },
    }


@pytest.fixture
def sample_scraped_articles():
    return pd.DataFrame(
        [
            {
                "record_id": "gdelt-1",
                "source": "gdelt",
                "source_type": "news",
                "url": "https://example.com/article",
                "published_at": "2026-06-24T12:30:00Z",
                "retrieved_at": "2026-06-24T13:00:00Z",
                "title": "Storm causes outage",
                "text": "Thousands lost power.",
                "text_length": 21,
                "scrape_status": "success",
                "success": True,
                "region": None,
                "categories": ["news", "gdelt"],
                "metadata": {
                    "method": "trafilatura",
                    "published_at_source": "json_ld",
                },
                "raw": {},
            }
        ]
    )

@pytest.fixture
def miso_source():
    return MISONotificationSource()

@pytest.fixture
def miso_make_raw_record():
    def _make(**notification_overrides):
        notification = {
            "id": "notif-123",
            "subject": "Market Notice",
            "publishDate": "2026-01-15T12:00:00Z",
            "body": "<p>Notification Body</p>",
            "permanentLinkUrl": "/markets/notice/123"
        }
        notification.update(notification_overrides)
        return {
            "topic": "Market Notice",
            "notification": notification
        }
    return _make

