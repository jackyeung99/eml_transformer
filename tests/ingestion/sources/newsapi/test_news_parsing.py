import pytest 

from datetime import datetime, timezone

from eml_transformer.ingestion.schema import BronzeRecord
from eml_transformer.utils.stamping import stable_hash


class TestBuildBronzeRecords:
    """Test the _build_bronze_records method."""

    def test_empty_response_returns_empty_list(self, newsapi_source):
        result = newsapi_source._build_bronze_records({})

        assert result == []

    def test_missing_articles_key_returns_empty_list(
        self,
        newsapi_source,
    ):
        result = newsapi_source._build_bronze_records(
            {"status": "ok"}
        )

        assert result == []

    def test_returns_bronze_records(self, newsapi_source):
        articles = [
            {
                "title": "First",
                "url": "https://example.com/first",
                "publishedAt": "2026-01-15T12:00:00Z",
            },
            {
                "title": "Second",
                "url": "https://example.com/second",
                "publishedAt": "2026-01-15T13:00:00Z",
            },
        ]

        result = newsapi_source._build_bronze_records(
            {
                "status": "ok",
                "articles": articles,
            }
        )

        assert len(result) == 2
        assert all(
            isinstance(record, BronzeRecord)
            for record in result
        )

        first = result[0]

        assert first.source == "newsapi"
        assert first.raw == articles[0]
        assert first.published_at == datetime(
            2026,
            1,
            15,
            12,
            0,
            tzinfo=timezone.utc,
        )
        assert first.retrieved_at.tzinfo is not None
        assert first.record_id == (
            "newsapi:"
            + stable_hash(
                {"url": "https://example.com/first"}
            )
        )

    def test_skips_article_missing_url(self, newsapi_source):
        result = newsapi_source._build_bronze_records(
            {
                "articles": [
                    {
                        "title": "Missing URL",
                        "publishedAt": "2026-01-15T12:00:00Z",
                    }
                ]
            }
        )

        assert result == []

    def test_skips_article_missing_published_at(
        self,
        newsapi_source,
    ):
        result = newsapi_source._build_bronze_records(
            {
                "articles": [
                    {
                        "title": "Missing timestamp",
                        "url": "https://example.com/article",
                    }
                ]
            }
        )

        assert result == []

    def test_skips_non_dictionary_articles(self, newsapi_source):
        valid_article = {
            "title": "Valid",
            "url": "https://example.com/valid",
            "publishedAt": "2026-01-15T12:00:00Z",
        }

        result = newsapi_source._build_bronze_records(
            {
                "articles": [
                    None,
                    "invalid",
                    valid_article,
                ]
            }
        )

        assert len(result) == 1
        assert result[0].raw == valid_article

    def test_deduplicates_articles_by_record_id(
        self,
        newsapi_source,
    ):
        article = {
            "title": "Duplicate",
            "url": "https://example.com/duplicate",
            "publishedAt": "2026-01-15T12:00:00Z",
        }

        result = newsapi_source._build_bronze_records(
            {
                "articles": [
                    article,
                    dict(article),
                ]
            }
        )

        assert len(result) == 1

    def test_raises_when_articles_is_not_a_list(
        self,
        newsapi_source,
    ):
        result = {
            "status": "ok",
            "articles": {"title": "Not a list"},
        }

        with pytest.raises(
            ValueError,
            match="articles.*must be a list",
        ):
            newsapi_source._build_bronze_records(result)