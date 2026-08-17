from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from eml_transformer.schema.records import (
    BronzeRecord,
    TextRecord,
)
from eml_transformer.sources.text.newsapi import (
    NewsAPISource,
)


UTC = timezone.utc

PUBLISHED_AT = datetime(
    2026,
    1,
    15,
    12,
    0,
    tzinfo=UTC,
)
RETRIEVED_AT = datetime(
    2026,
    1,
    15,
    12,
    5,
    tzinfo=UTC,
)


def make_newsapi_article(
    **overrides: Any,
) -> dict[str, Any]:
    article = {
        "source": {
            "id": "cnn",
            "name": "CNN",
        },
        "author": "John Reporter",
        "title": "Storm hits coast",
        "description": (
            "A severe storm caused damage."
        ),
        "content": "Full article content here.",
        "url": "https://example.com/article-1",
        "publishedAt": (
            "2026-01-15T12:00:00Z"
        ),
    }
    article.update(overrides)

    return article


@pytest.fixture
def newsapi_source() -> NewsAPISource:
    return NewsAPISource(
        api_key="test-key",
        query="storm",
    )


@pytest.fixture
def newsapi_make_bronze_record():
    def make_bronze_record(
        *,
        record_id: str = (
            "newsapi:test-record-id"
        ),
        published_at: datetime | None = None,
        retrieved_at: datetime | None = None,
        **article_overrides: Any,
    ) -> BronzeRecord:
        return BronzeRecord(
            source="newsapi",
            record_id=record_id,
            published_at=(
                published_at or PUBLISHED_AT
            ),
            retrieved_at=(
                retrieved_at or RETRIEVED_AT
            ),
            raw=make_newsapi_article(
                **article_overrides
            ),
        )

    return make_bronze_record


class TestStandardizeRecord:
    def test_returns_text_record(
        self,
        newsapi_source,
        newsapi_make_bronze_record,
    ):
        bronze = newsapi_make_bronze_record()

        record = newsapi_source.standardize_record(
            bronze
        )

        assert isinstance(record, TextRecord)

    def test_maps_basic_fields(
        self,
        newsapi_source,
        newsapi_make_bronze_record,
    ):
        bronze = newsapi_make_bronze_record()

        record = newsapi_source.standardize_record(
            bronze
        )

        assert record.source == "newsapi"
        assert record.source_type == "api"
        assert record.title == "Storm hits coast"
        assert record.url == (
            "https://example.com/article-1"
        )
        assert record.published_at == PUBLISHED_AT
        assert record.retrieved_at == RETRIEVED_AT
        assert record.region is None

    def test_combines_text_fields(
        self,
        newsapi_source,
        newsapi_make_bronze_record,
    ):
        bronze = newsapi_make_bronze_record()

        record = newsapi_source.standardize_record(
            bronze
        )

        assert record.text == (
            "Storm hits coast\n\n"
            "A severe storm caused damage.\n\n"
            "Full article content here."
        )

    def test_skips_none_text_parts(
        self,
        newsapi_source,
        newsapi_make_bronze_record,
    ):
        bronze = newsapi_make_bronze_record(
            description=None,
            content=None,
        )

        record = newsapi_source.standardize_record(
            bronze
        )

        assert record.text == "Storm hits coast"
        assert "None" not in record.text

    def test_skips_empty_text_parts(
        self,
        newsapi_source,
        newsapi_make_bronze_record,
    ):
        bronze = newsapi_make_bronze_record(
            description="",
            content="",
        )

        record = newsapi_source.standardize_record(
            bronze
        )

        assert record.text == "Storm hits coast"

    def test_handles_all_text_fields_missing(
        self,
        newsapi_source,
        newsapi_make_bronze_record,
    ):
        bronze = newsapi_make_bronze_record(
            title=None,
            description=None,
            content=None,
        )

        record = newsapi_source.standardize_record(
            bronze
        )

        assert record.text == ""

    def test_categories_contains_news(
        self,
        newsapi_source,
        newsapi_make_bronze_record,
    ):
        bronze = newsapi_make_bronze_record()

        record = newsapi_source.standardize_record(
            bronze
        )

        assert record.categories == ["news"]

    def test_metadata_captures_source_information(
        self,
        newsapi_source,
        newsapi_make_bronze_record,
    ):
        bronze = newsapi_make_bronze_record()

        record = newsapi_source.standardize_record(
            bronze
        )

        assert record.metadata[
            "news_source"
        ] == "CNN"
        assert record.metadata[
            "news_source_id"
        ] == "cnn"
        assert record.metadata[
            "author"
        ] == "John Reporter"
        assert record.metadata["query"] == "storm"
        assert record.metadata["language"] == "en"
        assert record.metadata[
            "sort_by"
        ] == "relevancy"

    @pytest.mark.parametrize(
        "source_value",
        [
            None,
            "CNN",
        ],
    )
    def test_handles_invalid_source_metadata(
        self,
        newsapi_source,
        newsapi_make_bronze_record,
        source_value,
    ):
        bronze = newsapi_make_bronze_record(
            source=source_value
        )

        record = newsapi_source.standardize_record(
            bronze
        )

        assert record.metadata[
            "news_source"
        ] is None
        assert record.metadata[
            "news_source_id"
        ] is None

    def test_preserves_bronze_record_id(
        self,
        newsapi_source,
        newsapi_make_bronze_record,
    ):
        bronze = newsapi_make_bronze_record(
            record_id="newsapi:expected-id"
        )

        record = newsapi_source.standardize_record(
            bronze
        )

        assert record.record_id == (
            "newsapi:expected-id"
        )

    def test_preserves_bronze_timestamps(
        self,
        newsapi_source,
        newsapi_make_bronze_record,
    ):
        published_at = datetime(
            2026,
            2,
            1,
            tzinfo=UTC,
        )
        retrieved_at = datetime(
            2026,
            2,
            2,
            tzinfo=UTC,
        )

        bronze = newsapi_make_bronze_record(
            published_at=published_at,
            retrieved_at=retrieved_at,
        )

        record = newsapi_source.standardize_record(
            bronze
        )

        assert record.published_at == published_at
        assert record.retrieved_at == retrieved_at

    def test_different_bronze_ids_remain_different(
        self,
        newsapi_source,
        newsapi_make_bronze_record,
    ):
        first_bronze = newsapi_make_bronze_record(
            record_id="newsapi:first",
            url="https://example.com/1",
            title="First",
        )
        second_bronze = newsapi_make_bronze_record(
            record_id="newsapi:second",
            url="https://example.com/2",
            title="Second",
        )

        first = newsapi_source.standardize_record(
            first_bronze
        )
        second = newsapi_source.standardize_record(
            second_bronze
        )

        assert first.record_id == "newsapi:first"
        assert second.record_id == "newsapi:second"
        assert first.record_id != second.record_id