from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch

import pytest
import requests

from eml_transformer.ingestion.schema import BronzeRecord
from eml_transformer.ingestion.sources.weather_alerts import (
    WeatherAlertSource,
)


class TestFetchArea:
    """Test the _fetch_area method."""

    def test_calls_correct_url(self, weather_source):
        mock_response = MagicMock()
        mock_response.json.return_value = {"features": []}

        with patch.object(
            weather_source._session,
            "get",
            return_value=mock_response,
        ) as mock_get:
            weather_source._fetch_area("IN")

        assert mock_get.call_args.args[0] == weather_source.BASE_URL

    def test_passes_area_param(self, weather_source):
        mock_response = MagicMock()
        mock_response.json.return_value = {"features": []}

        with patch.object(
            weather_source._session,
            "get",
            return_value=mock_response,
        ) as mock_get:
            weather_source._fetch_area("IN")

        assert mock_get.call_args.kwargs["params"] == {
            "area": "IN"
        }

    def test_passes_headers(self, weather_source):
        mock_response = MagicMock()
        mock_response.json.return_value = {"features": []}

        with patch.object(
            weather_source._session,
            "get",
            return_value=mock_response,
        ) as mock_get:
            weather_source._fetch_area("IN")

        headers = mock_get.call_args.kwargs["headers"]

        assert headers["User-Agent"] == (
            "eml-transformer-research"
        )
        assert headers["Accept"] == "application/geo+json"

    def test_passes_timeout(self, weather_source):
        mock_response = MagicMock()
        mock_response.json.return_value = {"features": []}

        with patch.object(
            weather_source._session,
            "get",
            return_value=mock_response,
        ) as mock_get:
            weather_source._fetch_area("IN")

        assert (
            mock_get.call_args.kwargs["timeout"]
            == weather_source.timeout
        )

    def test_returns_json_response(self, weather_source):
        payload = {
            "features": [
                {
                    "id": "a1",
                    "properties": {
                        "id": "a1",
                        "sent": "2026-01-15T12:00:00Z",
                    },
                }
            ]
        }
        mock_response = MagicMock()
        mock_response.json.return_value = payload

        with patch.object(
            weather_source._session,
            "get",
            return_value=mock_response,
        ):
            result = weather_source._fetch_area("IN")

        assert result == payload

    def test_raises_on_http_error(self, weather_source):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = (
            requests.HTTPError("500")
        )

        with patch.object(
            weather_source._session,
            "get",
            return_value=mock_response,
        ):
            with pytest.raises(requests.HTTPError):
                weather_source._fetch_area("IN")


class TestFetchRecords:
    """Test the fetch_records method."""

    def test_returns_empty_when_no_alerts(self, weather_source):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "features": [],
        }

        with patch.object(
            weather_source._session,
            "get",
            return_value=mock_response,
        ):
            result = weather_source.fetch_records()

        assert result == []

    def test_returns_bronze_records(
        self,
        weather_source,
        weather_make_feature,
    ):
        first_feature = weather_make_feature(id="a1")
        second_feature = weather_make_feature(id="a2")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "features": [
                first_feature,
                second_feature,
            ],
        }

        with patch.object(
            weather_source._session,
            "get",
            return_value=mock_response,
        ):
            result = weather_source.fetch_records()

        assert len(result) == 2
        assert all(
            isinstance(record, BronzeRecord)
            for record in result
        )

        first = result[0]

        assert first.source == "weather_alerts"
        assert first.record_id == "a1"
        assert first.raw == {
            "query_area": "IN",
            "feature": first_feature,
        }
        assert first.published_at == datetime(
            2026,
            1,
            15,
            12,
            0,
            tzinfo=timezone.utc,
        )
        assert first.retrieved_at.tzinfo is not None

    def test_makes_one_request_per_area(
        self,
        weather_make_feature,
    ):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "features": [],
        }
        mock_session.get.return_value = mock_response

        source = WeatherAlertSource(
            areas=["IN", "OH", "KY"],
            session=mock_session,
        )

        result = source.fetch_records()

        assert result == []
        assert mock_session.get.call_count == 3

        assert mock_session.get.call_args_list == [
            call(
                source.BASE_URL,
                params={"area": "IN"},
                headers=source.headers,
                timeout=source.timeout,
            ),
            call(
                source.BASE_URL,
                params={"area": "OH"},
                headers=source.headers,
                timeout=source.timeout,
            ),
            call(
                source.BASE_URL,
                params={"area": "KY"},
                headers=source.headers,
                timeout=source.timeout,
            ),
        ]

    def test_deduplicates_across_areas(
        self,
        weather_make_feature,
    ):
        mock_session = MagicMock()
        mock_response = MagicMock()

        shared_alert = weather_make_feature(id="shared-1")
        mock_response.json.return_value = {
            "features": [shared_alert],
        }
        mock_session.get.return_value = mock_response

        source = WeatherAlertSource(
            areas=["IN", "OH"],
            session=mock_session,
        )

        result = source.fetch_records()

        assert len(result) == 1
        assert result[0].record_id == "shared-1"

    def test_continues_when_one_area_request_fails(
        self,
        weather_make_feature,
    ):
        mock_session = MagicMock()

        failed_response = MagicMock()
        failed_response.raise_for_status.side_effect = (
            requests.HTTPError("500")
        )

        successful_response = MagicMock()
        successful_response.json.return_value = {
            "features": [
                weather_make_feature(id="oh-alert")
            ],
        }

        mock_session.get.side_effect = [
            failed_response,
            successful_response,
        ]

        source = WeatherAlertSource(
            areas=["IN", "OH"],
            session=mock_session,
        )

        result = source.fetch_records()

        assert len(result) == 1
        assert result[0].record_id == "oh-alert"
        assert result[0].raw["query_area"] == "OH"


class TestBuildBronzeRecords:
    """Test the _build_bronze_records method."""

    def test_empty_response_returns_empty_list(
        self,
        weather_source,
    ):
        result = weather_source._build_bronze_records(
            query_area="IN",
            raw_response={},
        )

        assert result == []

    def test_returns_bronze_records(
        self,
        weather_source,
        weather_make_feature,
    ):
        feature = weather_make_feature(id="alert-1")

        result = weather_source._build_bronze_records(
            query_area="IN",
            raw_response={"features": [feature]},
        )

        assert len(result) == 1

        record = result[0]

        assert isinstance(record, BronzeRecord)
        assert record.source == "weather_alerts"
        assert record.record_id == "alert-1"
        assert record.raw["query_area"] == "IN"
        assert record.raw["feature"] == feature

    def test_returns_empty_when_features_is_not_a_list(
        self,
        weather_source,
    ):
        result = weather_source._build_bronze_records(
            query_area="IN",
            raw_response={"features": {"id": "invalid"}},
        )

        assert result == []

    def test_skips_non_dictionary_feature(
        self,
        weather_source,
        weather_make_feature,
    ):
        valid_feature = weather_make_feature(id="valid")

        result = weather_source._build_bronze_records(
            query_area="IN",
            raw_response={
                "features": [
                    None,
                    "invalid",
                    valid_feature,
                ]
            },
        )

        assert len(result) == 1
        assert result[0].record_id == "valid"

    def test_skips_feature_missing_id(
        self,
        weather_source,
        weather_make_feature,
    ):
        feature = weather_make_feature(id=None)

        result = weather_source._build_bronze_records(
            query_area="IN",
            raw_response={"features": [feature]},
        )

        assert result == []

    def test_skips_feature_missing_sent_timestamp(
        self,
        weather_source,
        weather_make_feature,
    ):
        feature = weather_make_feature(id="alert-1")
        feature["properties"]["sent"] = None

        result = weather_source._build_bronze_records(
            query_area="IN",
            raw_response={"features": [feature]},
        )

        assert result == []

    def test_skips_feature_with_invalid_sent_timestamp(
        self,
        weather_source,
        weather_make_feature,
    ):
        feature = weather_make_feature(id="alert-1")
        feature["properties"]["sent"] = "invalid"

        result = weather_source._build_bronze_records(
            query_area="IN",
            raw_response={"features": [feature]},
        )

        assert result == []