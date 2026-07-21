import pytest
from unittest.mock import MagicMock, patch


class TestFetchPage:
    """Test the _fetch_page method."""

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_calls_correct_url(self, mock_get, newsapi_source):
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok", "articles": []}
        mock_get.return_value = mock_response

        newsapi_source._fetch_page(page=1)

        called_url = mock_get.call_args[0][0]
        assert called_url == newsapi_source.base_url

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_passes_query_params(self, mock_get, newsapi_source):
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok", "articles": []}
        mock_get.return_value = mock_response

        newsapi_source._fetch_page(page=1)

        params = mock_get.call_args[1]["params"]
        assert params["q"] == "storm"
        assert params["language"] == "en"
        assert params["sortBy"] == "relevancy"
        assert params["pageSize"] == 100
        assert params["page"] == 1
        assert params["apiKey"] == "test-key"

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_includes_from_date_when_provided(self, mock_get, newsapi_source):
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok", "articles": []}
        mock_get.return_value = mock_response

        newsapi_source._fetch_page(page=1, from_date="2026-01-01")

        params = mock_get.call_args[1]["params"]
        assert params["from"] == "2026-01-01"

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_omits_from_date_when_none(self, mock_get, newsapi_source):
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok", "articles": []}
        mock_get.return_value = mock_response

        newsapi_source._fetch_page(page=1)

        params = mock_get.call_args[1]["params"]
        assert "from" not in params

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_raises_on_http_error(self, mock_get, newsapi_source):
        import requests
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("500")
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
            "articles": [{"title": "First"}, {"title": "Second"}],
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
        mock_response.json.return_value = {"status": "ok", "articles": []}
        mock_get.return_value = mock_response

        result = newsapi_source._fetch_raw()

        assert result["articles"] == []
        assert mock_get.call_count == 1  # stopped after first empty page

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_raises_on_non_ok_status(self, mock_get, newsapi_source):
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "error", "message": "Bad key"}
        mock_get.return_value = mock_response

        with pytest.raises(RuntimeError, match="NewsAPI request failed"):
            newsapi_source._fetch_raw()

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_stops_when_page_smaller_than_page_size(self, mock_get, newsapi_source):
        newsapi_source.max_pages = 5
        newsapi_source.page_size = 100
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "totalResults": 5,
            "articles": [{"title": f"Article {i}"} for i in range(5)],
        }
        mock_get.return_value = mock_response

        result = newsapi_source._fetch_raw()

        # Only 5 articles returned (less than page_size 100), so should stop after page 1
        assert len(result["articles"]) == 5
        assert mock_get.call_count == 1

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_paginates_across_multiple_pages(self, mock_get, newsapi_source):
        newsapi_source.max_pages = 3
        newsapi_source.page_size = 2

        # Return 2 full pages, then an empty one
        mock_response = MagicMock()
        mock_response.json.side_effect = [
            {"status": "ok", "totalResults": 5, "articles": [{"t": "1"}, {"t": "2"}]},
            {"status": "ok", "totalResults": 5, "articles": [{"t": "3"}, {"t": "4"}]},
            {"status": "ok", "totalResults": 5, "articles": [{"t": "5"}]},
        ]
        mock_get.return_value = mock_response

        result = newsapi_source._fetch_raw()

        assert len(result["articles"]) == 5
        assert mock_get.call_count == 3

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_uses_instance_from_date_as_fallback(self, mock_get, newsapi_source):
        newsapi_source.from_date = "2026-01-01"
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok", "articles": []}
        mock_get.return_value = mock_response

        newsapi_source._fetch_raw()

        params = mock_get.call_args[1]["params"]
        assert params["from"] == "2026-01-01"

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_explicit_from_date_overrides_instance(self, mock_get, newsapi_source):
        newsapi_source.from_date = "2026-01-01"
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok", "articles": []}
        mock_get.return_value = mock_response

        newsapi_source._fetch_raw(from_date="2026-06-01")

        params = mock_get.call_args[1]["params"]
        assert params["from"] == "2026-06-01"


class TestFetchRecords:
    """Test the fetch_records method."""

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_returns_empty_when_no_articles(self, mock_get, newsapi_source):
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok", "articles": []}
        mock_get.return_value = mock_response

        result = newsapi_source.fetch_records()
        assert result == []

    @patch("eml_transformer.ingestion.sources.newsapi.requests.get")
    def test_returns_articles_list(self, mock_get, newsapi_source):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "totalResults": 2,
            "articles": [{"title": "First"}, {"title": "Second"}],
        }
        mock_get.return_value = mock_response

        result = newsapi_source.fetch_records()
        assert len(result) == 2
        assert result[0]["title"] == "First"