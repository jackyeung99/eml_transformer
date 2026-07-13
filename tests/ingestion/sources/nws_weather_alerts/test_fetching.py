import pytest
from unittest.mock import MagicMock, patch


class TestFetchRaw:
    """Test the _fetch_raw method."""

    @patch("eml_transformer.ingestion.sources.weather_alerts.requests.get")
    def test_calls_correct_url(self, mock_get, weather_source):
        mock_response = MagicMock()
        mock_response.json.return_value = {"features": []}
        mock_get.return_value = mock_response

        weather_source._fetch_raw()

        called_url = mock_get.call_args[0][0]
        assert called_url == weather_source.base_url

    @patch("eml_transformer.ingestion.sources.weather_alerts.requests.get")
    def test_passes_area_param(self, mock_get, weather_source):
        mock_response = MagicMock()
        mock_response.json.return_value = {"features": []}
        mock_get.return_value = mock_response

        weather_source._fetch_raw()

        params = mock_get.call_args[1]["params"]
        assert params["area"] == "IN"

    @patch("eml_transformer.ingestion.sources.weather_alerts.requests.get")
    def test_passes_headers(self, mock_get, weather_source):
        mock_response = MagicMock()
        mock_response.json.return_value = {"features": []}
        mock_get.return_value = mock_response

        weather_source._fetch_raw()

        headers = mock_get.call_args[1]["headers"]
        assert "User-Agent" in headers
        assert headers["Accept"] == "application/geo+json"

    @patch("eml_transformer.ingestion.sources.weather_alerts.requests.get")
    def test_passes_timeout(self, mock_get, weather_source):
        mock_response = MagicMock()
        mock_response.json.return_value = {"features": []}
        mock_get.return_value = mock_response

        weather_source._fetch_raw()

        assert mock_get.call_args[1]["timeout"] == weather_source.timeout

    @patch("eml_transformer.ingestion.sources.weather_alerts.requests.get")
    def test_returns_list_with_query_area_and_response(self, mock_get, weather_source):
        mock_response = MagicMock()
        mock_response.json.return_value = {"features": [{"id": "a1"}]}
        mock_get.return_value = mock_response

        result = weather_source._fetch_raw()

        assert len(result) == 1
        assert result[0]["query_area"] == "IN"
        assert result[0]["response"] == {"features": [{"id": "a1"}]}

    @patch("eml_transformer.ingestion.sources.weather_alerts.requests.get")
    def test_makes_one_request_per_area(self, mock_get):
        from eml_transformer.ingestion.sources.weather_alerts import WeatherAlertSource
        source = WeatherAlertSource(areas=["IN", "OH", "KY"])

        mock_response = MagicMock()
        mock_response.json.return_value = {"features": []}
        mock_get.return_value = mock_response

        result = source._fetch_raw()

        assert mock_get.call_count == 3
        assert len(result) == 3
        assert result[0]["query_area"] == "IN"
        assert result[1]["query_area"] == "OH"
        assert result[2]["query_area"] == "KY"

    @patch("eml_transformer.ingestion.sources.weather_alerts.requests.get")
    def test_raises_on_http_error(self, mock_get, weather_source):
        import requests
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("500")
        mock_get.return_value = mock_response

        with pytest.raises(requests.HTTPError):
            weather_source._fetch_raw()


class TestFetchRecords:
    """Test the fetch_records method."""

    @patch("eml_transformer.ingestion.sources.weather_alerts.requests.get")
    def test_returns_empty_when_no_alerts(self, mock_get, weather_source):
        mock_response = MagicMock()
        mock_response.json.return_value = {"features": []}
        mock_get.return_value = mock_response

        result = weather_source.fetch_records()
        assert result == []

    @patch("eml_transformer.ingestion.sources.weather_alerts.requests.get")
    def test_returns_parsed_records(self, mock_get, weather_source, weather_make_feature):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "features": [
                weather_make_feature(id="a1"),
                weather_make_feature(id="a2"),
            ],
        }
        mock_get.return_value = mock_response

        result = weather_source.fetch_records()
        assert len(result) == 2
        assert result[0]["query_area"] == "IN"

    @patch("eml_transformer.ingestion.sources.weather_alerts.requests.get")
    def test_deduplicates_across_areas(self, mock_get, weather_make_feature):
        """Same alert across multiple states should only be returned once."""
        from eml_transformer.ingestion.sources.weather_alerts import WeatherAlertSource
        source = WeatherAlertSource(areas=["IN", "OH"])

        shared_alert = weather_make_feature(id="shared-1")
        mock_response = MagicMock()
        mock_response.json.return_value = {"features": [shared_alert]}
        mock_get.return_value = mock_response

        result = source.fetch_records()
        assert len(result) == 1