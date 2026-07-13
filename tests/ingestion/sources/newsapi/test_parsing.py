import pytest


class TestParseRecords:
    """Test the _parse_records method"""

    def test_empty_response_returns_empty_list(self, newsapi_source):
        result = newsapi_source._parse_records({})
        assert result == []

    def test_returns_articles_list(self, newsapi_source):
        raw = {
            "status": "ok",
            "articles": [{"title": "First"}, {"title": "Second"}]
        }
        result = newsapi_source._parse_records(raw)

        assert len(result) == 2
        assert result[0]["title"] == "First"
    
    def test_missing_articles_key_returns_empty(self, newsapi_source):
        raw = {"status": "ok"}
        result = newsapi_source._parse_records(raw)

        assert result == []


class TestGetCheckpointValue:
    """Test the get_checkpoint_value method"""

    def test_returns_published_at(self, newsapi_source):
        raw = {"title": "Title", "publishedAt": "2026-01-15T12:00:00Z"}
        assert newsapi_source.get_checkpoint_value(raw) == "2026-01-15T12:00:00Z"
    
    def test_returns_none_when_missing(self, newsapi_source):
        assert newsapi_source.get_checkpoint_value({}) is None
    
        