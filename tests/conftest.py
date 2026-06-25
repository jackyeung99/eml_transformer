from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import pytest

from eml_transformer.storage.paths import StoragePaths


class FakeStorage:
    def __init__(self):
        self.data: dict[str, pd.DataFrame] = {}

    def write_parquet(self, df: pd.DataFrame, key: str) -> None:
        self.data[key] = df.copy()

    def read_parquet(self, key: str) -> pd.DataFrame:
        if key not in self.data:
            raise FileNotFoundError(key)
        return self.data[key].copy()

    def exists(self, key: str) -> bool:
        return key in self.data


class FakeSource:
    name = "gdelt"
    source_type = "news"

    def fetch_raw(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "record_id": "gdelt-1",
                    "url": "https://example.com/article",
                    "title": "Raw title",
                    "text": "Raw text",
                    "published_at": "2026-06-24T12:00:00Z",
                    "metadata": {"raw": True},
                }
            ]
        )

    def parse_records(self, raw: pd.DataFrame) -> list[dict[str, Any]]:
        return raw.to_dict("records")

    def standardize_record(self, record: dict[str, Any]) -> dict[str, Any]:
        return {
            "record_id": record["record_id"],
            "source": self.name,
            "source_type": self.source_type,
            "title": record.get("title"),
            "text": record.get("text"),
            "published_at": record.get("published_at"),
            "retrieved_at": "2026-06-24T13:00:00Z",
            "url": record.get("url"),
            "region": None,
            "categories": ["news", "gdelt"],
            "metadata": record.get("metadata", {}),
            "raw": record,
        }


class FakeScraper:
    def __init__(self, result: dict[str, Any] | None = None, exc: Exception | None = None):
        self.result = result or {}
        self.exc = exc
        self.urls_seen: list[str] = []

    async def scrape(self, session, url: str) -> dict[str, Any]:
        self.urls_seen.append(url)

        if self.exc:
            raise self.exc

        return self.result


class FakeEmbeddingModel:
    def __init__(self):
        self.texts_seen: list[str] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.texts_seen.extend(texts)
        return [[0.1, 0.2, 0.3] for _ in texts]


@pytest.fixture
def storage():
    return FakeStorage()


@pytest.fixture
def paths():
    return StoragePaths()


@pytest.fixture
def fake_source():
    return FakeSource()


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
def fake_scraper(sample_scraped_article):
    return FakeScraper(result=sample_scraped_article)


@pytest.fixture
def failing_scraper():
    return FakeScraper(exc=RuntimeError("boom"))


@pytest.fixture
def embedding_model():
    return FakeEmbeddingModel()