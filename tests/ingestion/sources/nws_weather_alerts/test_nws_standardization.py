from datetime import datetime, timezone

from eml_transformer.ingestion.schema import (
    BronzeRecord,
    TextRecord,
)


class TestStandardizeRecord:
    """Test the standardize_record method."""

    def _make_bronze(
        self,
        weather_make_feature,
        query_area="IN",
        record_id="alert-123",
        **property_overrides,
    ):
        feature = weather_make_feature(
            id=record_id,
            **property_overrides,
        )

        return BronzeRecord(
            source="weather_alerts",
            record_id=record_id,
            published_at=datetime(
                2026,
                1,
                15,
                12,
                0,
                tzinfo=timezone.utc,
            ),
            retrieved_at=datetime(
                2026,
                1,
                15,
                12,
                5,
                tzinfo=timezone.utc,
            ),
            raw={
                "query_area": query_area,
                "feature": feature,
            },
        )

    def test_returns_text_record(
        self,
        weather_source,
        weather_make_feature,
    ):
        bronze = self._make_bronze(weather_make_feature)

        record = weather_source.standardize_record(bronze)

        assert isinstance(record, TextRecord)

    def test_maps_basic_fields(
        self,
        weather_source,
        weather_make_feature,
    ):
        bronze = self._make_bronze(weather_make_feature)

        record = weather_source.standardize_record(bronze)

        assert record.source == "weather_alerts"
        assert record.source_type == "api"
        assert record.title == "Severe Thunderstorm Warning"
        assert record.url == (
            "https://api.weather.gov/alerts/alert-123"
        )
        assert record.published_at == datetime(
            2026,
            1,
            15,
            12,
            0,
            tzinfo=timezone.utc,
        )

    def test_region_is_query_area(
        self,
        weather_source,
        weather_make_feature,
    ):
        bronze = self._make_bronze(
            weather_make_feature,
            query_area="OH",
        )

        record = weather_source.standardize_record(bronze)

        assert record.region == "OH"

    def test_combines_text_fields(
        self,
        weather_source,
        weather_make_feature,
    ):
        bronze = self._make_bronze(weather_make_feature)

        record = weather_source.standardize_record(bronze)

        assert record.text == (
            "Severe Thunderstorm Warning\n\n"
            "Damaging winds expected.\n\n"
            "Take shelter immediately"
        )

    def test_skips_none_parts_in_text(
        self,
        weather_source,
        weather_make_feature,
    ):
        bronze = self._make_bronze(
            weather_make_feature,
            description=None,
            instruction=None,
        )

        record = weather_source.standardize_record(bronze)

        assert record.text == "Severe Thunderstorm Warning"

    def test_skips_empty_parts_in_text(
        self,
        weather_source,
        weather_make_feature,
    ):
        bronze = self._make_bronze(
            weather_make_feature,
            description="",
            instruction="",
        )

        record = weather_source.standardize_record(bronze)

        assert record.text == "Severe Thunderstorm Warning"

    def test_categories_include_event_severity_and_urgency(
        self,
        weather_source,
        weather_make_feature,
    ):
        bronze = self._make_bronze(weather_make_feature)

        record = weather_source.standardize_record(bronze)

        assert record.categories == [
            "Severe Thunderstorm Warning",
            "Severe",
            "Immediate",
        ]

    def test_metadata_captures_alert_fields(
        self,
        weather_source,
        weather_make_feature,
    ):
        bronze = self._make_bronze(weather_make_feature)

        record = weather_source.standardize_record(bronze)

        assert record.metadata["query_area"] == "IN"
        assert (
            record.metadata["event"]
            == "Severe Thunderstorm Warning"
        )
        assert record.metadata["severity"] == "Severe"
        assert record.metadata["urgency"] == "Immediate"
        assert record.metadata["certainty"] == "Observed"
        assert record.metadata["status"] == "Actual"
        assert record.metadata["message_type"] == "Alert"
        assert record.metadata["category"] == "Met"
        assert (
            record.metadata["sender_name"]
            == "NWS Indianapolis IN"
        )
        assert record.metadata["area_desc"] == "Marion, IN"

    def test_metadata_captures_time_fields(
        self,
        weather_source,
        weather_make_feature,
    ):
        bronze = self._make_bronze(weather_make_feature)

        record = weather_source.standardize_record(bronze)

        assert (
            record.metadata["effective_at"]
            == "2026-01-15T12:00:00Z"
        )
        assert (
            record.metadata["expires_at"]
            == "2026-01-15T13:00:00Z"
        )
        assert (
            record.metadata["ends_at"]
            == "2026-01-15T13:00:00Z"
        )

    def test_raw_field_contains_full_feature(
        self,
        weather_source,
        weather_make_feature,
    ):
        bronze = self._make_bronze(weather_make_feature)

        record = weather_source.standardize_record(bronze)

        assert record.raw == bronze.raw["feature"]

    def test_preserves_retrieved_at(
        self,
        weather_source,
        weather_make_feature,
    ):
        bronze = self._make_bronze(weather_make_feature)

        record = weather_source.standardize_record(bronze)

        assert record.retrieved_at == bronze.retrieved_at

    def test_preserves_record_id(
        self,
        weather_source,
        weather_make_feature,
    ):
        bronze = self._make_bronze(
            weather_make_feature,
            record_id="expected-alert-id",
        )

        record = weather_source.standardize_record(bronze)

        assert record.record_id == "expected-alert-id"

    def test_different_bronze_ids_remain_different(
        self,
        weather_source,
        weather_make_feature,
    ):
        first_bronze = self._make_bronze(
            weather_make_feature,
            record_id="alert-1",
            headline="First",
        )
        second_bronze = self._make_bronze(
            weather_make_feature,
            record_id="alert-2",
            headline="Second",
        )

        first = weather_source.standardize_record(first_bronze)
        second = weather_source.standardize_record(second_bronze)

        assert first.record_id == "alert-1"
        assert second.record_id == "alert-2"
        assert first.record_id != second.record_id

    def test_url_falls_back_to_feature_id(
        self,
        weather_source,
    ):
        feature = {
            "id": "fallback-feature-id",
            "properties": {
                "headline": "Test",
                "sent": "2026-01-15T12:00:00Z",
            },
        }
        bronze = BronzeRecord(
            source="weather_alerts",
            record_id="fallback-feature-id",
            published_at=datetime(
                2026,
                1,
                15,
                12,
                0,
                tzinfo=timezone.utc,
            ),
            retrieved_at=datetime(
                2026,
                1,
                15,
                12,
                5,
                tzinfo=timezone.utc,
            ),
            raw={
                "query_area": "IN",
                "feature": feature,
            },
        )

        record = weather_source.standardize_record(bronze)

        assert record.record_id == "fallback-feature-id"
        assert record.url == "fallback-feature-id"