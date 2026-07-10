import pytest
from unittest.mock import MagicMock, patch
import requests


class TestFetchRaw:
    """Test the _fetch_raw method"""

    @patch("eml_transformer.ingestion.sources.miso.requests.get")
    def test_calls_correct_url(self, mock_get, miso_source):
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        miso_source._fetch_raw()

        called_url = mock_get.call_args[0][0]
        assert called_url == miso_source.base_url

    @patch("eml_transformer.ingestion.sources.miso.requests.get")
    def test_passes_correct_params(self, mock_get, miso_source):
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        miso_source._fetch_raw()

        params = mock_get.call_args[1]["params"]
        assert params["topic"] == miso_source.topic
        assert params["take"] == miso_source.take
    
    @patch("eml_transformer.ingestion.sources.miso.requests.get")
    def test_passes_headers(self, mock_get, miso_source):
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        miso_source._fetch_raw()

        headers = mock_get.call_args[1]["headers"]
        assert "User-Agent" in headers
        assert "Referer" in headers

    @patch("eml_transformer.ingestion.sources.miso.requests.get")
    def test_passes_timeout(self, mock_get, miso_source):
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        miso_source._fetch_raw()

        assert mock_get.call_args[1]["timeout"] == miso_source.timeout

    @patch("eml_transformer.ingestion.sources.miso.requests.get")
    def test_returns_parsed_json(self, mock_get, miso_source):
        expected_data = [{"topic": "Test", "notifications": []}]
        mock_response = MagicMock()
        mock_response.json.return_value = expected_data
        mock_get.return_value = mock_response

        result = miso_source._fetch_raw()
        assert result == expected_data

    @patch("eml_transformer.ingestion.sources.miso.requests.get")
    def test_raises_on_http_error(self, mock_get, miso_source):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
        mock_get.return_value = mock_response

        with pytest.raises(requests.HTTPError):
            miso_source._fetch_raw()

class TestFetchRecords:
    """Test the fetch_records method"""

    @patch("eml_transformer.ingestion.sources.miso.requests.get")
    def test_returns_empty_when_no_data(self, mock_get, miso_source):
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        result = miso_source.fetch_records()
        assert result == []
    
    @patch("eml_transformer.ingestion.sources.miso.requests.get")
    def test_returns_parsed_records(self, mock_get, miso_source):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "topic": "Market Notice",
                "notifications": [
                    {"id": "1", "subject": "First"},
                    {"id": "2", "subject": "Second"}
                ]
            }
        ]
        mock_get.return_value = mock_response

        result = miso_source.fetch_records()
        assert len(result) == 2
        assert result[0]["topic"] == "Market Notice"
        assert result[0]["notification"]["id"] == "1"
        assert result[1]["notification"]["id"] == "2"

    @patch("eml_transformer.ingestion.sources.miso.requests.get")
    def test_flattens_multiple_topics(self, mock_get, miso_source):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"topic": "A", "notifications": [{"id": "1"}, {"id": "2"}]},
            {"topic": "B", "notifications": [{"id": "3"}]}
        ]
        mock_get.return_value = mock_response

        result = miso_source.fetch_records()
        assert len(result) == 3

