from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import pytest

from eml_transformer.storage.paths import StoragePaths
from tests.helpers import FakeEmbeddingModel, FakeScraper, FakeSource, FakeStorage, FakeIngestionPipeline
from eml_transformer.ingestion.sources.gdelt import GDELTSource
from eml_transformer.ingestion.sources.iem_afos import IEMAFOSSource
from eml_transformer.ingestion.sources.miso import MISONotificationSource
from eml_transformer.ingestion.sources.newsapi import NewsAPISource
from eml_transformer.ingestion.sources.weather_alerts import WeatherAlertSource

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
    return FakeSource()

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
            "body": "<p>Notification body</p>",
            "permanentLinkUrl": "/markets/notice/123",
        }
        notification.update(notification_overrides)
        return {
            "topic": "Market Notice",
            "notification": notification,
        }
    return _make

@pytest.fixture
def newsapi_source():
    return NewsAPISource(api_key="test-key", query="storm")

@pytest.fixture
def newsapi_make_article():
    def _make(**overrides):
        article = {
            "source": {"id": "cnn", "name": "CNN"},
            "author": "John Reporter",
            "title": "Storm hits coast",
            "description": "A severe storm caused damage.",
            "content": "Full article content here.",
            "url": "https://example.com/article-1",
            "publishedAt": "2026-01-15T12:00:00Z"
        }
        article.update(overrides)
        return article
    return _make

@pytest.fixture
def weather_source():
    return WeatherAlertSource(areas=["IN"])

@pytest.fixture
def weather_make_feature():
    def _make(**prop_overrides):
        properties = {
            "id": "alert-123",
            "@id": "https://api.weather.gov/alerts/alert-123",
            "headline": "Severe Thunderstorm Warning",
            "description": "Damaging winds expected.",
            "instruction": "Take shelter immediately",
            "event": "Severe Thunderstorm Warning",
            "severity": "Severe",
            "urgency": "Immediate",
            "certainty": "Observed",
            "status": "Actual",
            "messageType": "Alert",
            "category": "Met",
            "response": "Shelter",
            "sender": "w-nws.webmaster@noaa.gov",
            "senderName": "NWS Indianapolis IN",
            "areaDesc": "Marion, IN",
            "geocode": {"UGC": ["INC097"]},
            "affectedZones": ["https://api.weather.gov/zones/country/INC097"],
            "sent": "2026-01-15T12:00:00Z",
            "effective": "2026-01-15T12:00:00Z",
            "expires": "2026-01-15T13:00:00Z",
            "ends": "2026-01-15T13:00:00Z"
        }
        properties.update(prop_overrides)
        return {
            "id": properties["id"],
            "properties": properties
        }
    return _make
