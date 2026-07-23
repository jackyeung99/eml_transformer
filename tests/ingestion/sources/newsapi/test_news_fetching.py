from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests

from eml_transformer.ingestion.schema import BronzeRecord
from eml_transformer.utils.stamping import stable_hash


class TestFetchPage:
    """Test the _fetch_page method."""

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_calls_correct_url(self, mock_get, newsapi_source):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "articles": [],
        }
        mock_get.return_value = mock_response

        newsapi_source._fetch_page(page=1)

        assert mock_get.call_args.args[0] == newsapi_source.base_url

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_passes_query_params(self, mock_get, newsapi_source):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "articles": [],
        }
        mock_get.return_value = mock_response

        newsapi_source._fetch_page(page=1)

        params = mock_get.call_args.kwargs["params"]

        assert params["q"] == "storm"
        assert params["language"] == "en"
        assert params["sortBy"] == "relevancy"
        assert params["pageSize"] == 100
        assert params["page"] == 1
        assert params["apiKey"] == "test-key"

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_includes_date_window_when_provided(
        self,
        mock_get,
        newsapi_source,
    ):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "articles": [],
        }
        mock_get.return_value = mock_response

        from_date = datetime(
            2026,
            1,
            1,
            tzinfo=timezone.utc,
        )
        to_date = datetime(
            2026,
            1,
            31,
            23,
            59,
            59,
            tzinfo=timezone.utc,
        )

        newsapi_source._fetch_page(
            page=1,
            from_date=from_date,
            to_date=to_date,
        )

        params = mock_get.call_args.kwargs["params"]

        assert params["from"] == from_date.isoformat()
        assert params["to"] == to_date.isoformat()

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_omits_dates_when_none(self, mock_get, newsapi_source):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "articles": [],
        }
        mock_get.return_value = mock_response

        newsapi_source._fetch_page(page=1)

        params = mock_get.call_args.kwargs["params"]

        assert "from" not in params
        assert "to" not in params

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_raises_on_http_error(self, mock_get, newsapi_source):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError(
            "500"
        )
        mock_get.return_value = mock_response

        with pytest.raises(requests.HTTPError):
            newsapi_source._fetch_page(page=1)
class TestFetchRaw:
    """Test the _fetch_raw method."""

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_single_page_response(self, mock_get, newsapi_source):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "totalResults": 2,
            "articles": [
                {"title": "First", "url": "first_url"},
                {"title": "Second", "url": "second_url"},
            ],
        }
        mock_get.return_value = mock_response

        result = newsapi_source._fetch_raw()

        assert result["status"] == "ok"
        assert len(result["articles"]) == 2
        assert result["totalResults"] == 2

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_stops_when_articles_empty(self, mock_get, newsapi_source):
        newsapi_source.max_pages = 3

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "articles": [],
        }
        mock_get.return_value = mock_response

        result = newsapi_source._fetch_raw()

        assert result["articles"] == []
        assert mock_get.call_count == 1

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_raises_on_non_ok_status(self, mock_get, newsapi_source):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "error",
            "message": "Bad key",
        }
        mock_get.return_value = mock_response

        with pytest.raises(
            RuntimeError,
            match="NewsAPI request failed",
        ):
            newsapi_source._fetch_raw()

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_stops_when_page_smaller_than_page_size(
        self,
        mock_get,
        newsapi_source,
    ):
        newsapi_source.max_pages = 5
        newsapi_source.page_size = 100

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "totalResults": 5,
            "articles": [
                {"title": f"Article {index}"}
                for index in range(5)
            ],
        }
        mock_get.return_value = mock_response

        result = newsapi_source._fetch_raw()

        assert len(result["articles"]) == 5
        assert mock_get.call_count == 1

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_paginates_across_multiple_pages(
        self,
        mock_get,
        newsapi_source,
    ):
        newsapi_source.max_pages = 3
        newsapi_source.page_size = 2

        mock_response = MagicMock()
        mock_response.json.side_effect = [
            {
                "status": "ok",
                "totalResults": 5,
                "articles": [{"t": "1"}, {"t": "2"}],
            },
            {
                "status": "ok",
                "totalResults": 5,
                "articles": [{"t": "3"}, {"t": "4"}],
            },
            {
                "status": "ok",
                "totalResults": 5,
                "articles": [{"t": "5"}],
            },
        ]
        mock_get.return_value = mock_response

        result = newsapi_source._fetch_raw()

        assert len(result["articles"]) == 5
        assert mock_get.call_count == 3

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_passes_explicit_date_window(
        self,
        mock_get,
        newsapi_source,
    ):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "articles": [],
        }
        mock_get.return_value = mock_response

        from_date = datetime(
            2026,
            1,
            1,
            tzinfo=timezone.utc,
        )
        to_date = datetime(
            2026,
            6,
            1,
            tzinfo=timezone.utc,
        )

        newsapi_source._fetch_raw(
            from_date=from_date,
            to_date=to_date,
        )

        params = mock_get.call_args.kwargs["params"]

        assert params["from"] == from_date.isoformat()
        assert params["to"] == to_date.isoformat()

class TestFetchRecords:
    """Test the fetch_records method."""

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_returns_empty_when_no_articles(
        self,
        mock_get,
        newsapi_source,
    ):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "articles": [],
        }
        mock_get.return_value = mock_response

        result = newsapi_source.fetch_records()

        assert result == []

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_returns_bronze_records(
        self,
        mock_get,
        newsapi_source,
    ):
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

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "totalResults": 2,
            "articles": articles,
        }
        mock_get.return_value = mock_response

        result = newsapi_source.fetch_records()

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

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_skips_articles_missing_required_fields(
        self,
        mock_get,
        newsapi_source,
    ):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "totalResults": 3,
            "articles": [
                {
                    "title": "Valid",
                    "url": "https://example.com/valid",
                    "publishedAt": "2026-01-15T12:00:00Z",
                },
                {
                    "title": "Missing URL",
                    "publishedAt": "2026-01-15T12:00:00Z",
                },
                {
                    "title": "Missing timestamp",
                    "url": "https://example.com/missing-time",
                },
            ],
        }
        mock_get.return_value = mock_response

        result = newsapi_source.fetch_records()

        assert len(result) == 1
        assert result[0].raw["title"] == "Valid"

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_deduplicates_articles_by_record_id(
        self,
        mock_get,
        newsapi_source,
    ):
        article = {
            "title": "Duplicate",
            "url": "https://example.com/duplicate",
            "publishedAt": "2026-01-15T12:00:00Z",
        }

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "totalResults": 2,
            "articles": [article, dict(article)],
        }
        mock_get.return_value = mock_response

        result = newsapi_source.fetch_records()

        assert len(result) == 1