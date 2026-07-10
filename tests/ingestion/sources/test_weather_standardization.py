import pytest
from eml_transformer.ingestion.schema import TextRecord


class TestStandardizeRecord:
    """Test the standardize_record method."""

    def _make_raw(self, weather_make_feature, query_area="IN", **prop_overrides):
        return {
            "query_area": query_area,
            "feature": weather_make_feature(**prop_overrides),
        }

    def test_returns_text_record(self, weather_source, weather_make_feature):
        record = weather_source.standardize_record(self._make_raw(weather_make_feature))
        assert isinstance(record, TextRecord)

    def test_maps_basic_fields(self, weather_source, weather_make_feature):
        record = weather_source.standardize_record(self._make_raw(weather_make_feature))
        assert record.source == "weather_alerts"
        assert record.source_type == "api"
        assert record.title == "Severe Thunderstorm Warning"
        assert record.url == "https://api.weather.gov/alerts/alert-123"
        assert record.published_at == "2026-01-15T12:00:00Z"

    def test_region_is_query_area(self, weather_source, weather_make_feature):
        record = weather_source.standardize_record(
            self._make_raw(weather_make_feature, query_area="OH")
        )
        assert record.region == "OH"

    def test_combines_headline_description_instruction_into_text(self, weather_source, weather_make_feature):
        record = weather_source.standardize_record(self._make_raw(weather_make_feature))
        assert "Severe Thunderstorm Warning" in record.text
        assert "Damaging winds expected." in record.text
        assert "Take shelter immediately" in record.text

    def test_skips_none_parts_in_text(self, weather_source, weather_make_feature):
        raw = self._make_raw(weather_make_feature, description=None, instruction=None)
        record = weather_source.standardize_record(raw)
        assert record.text == "Severe Thunderstorm Warning"

    def test_skips_empty_parts_in_text(self, weather_source, weather_make_feature):
        raw = self._make_raw(weather_make_feature, description="", instruction="")
        record = weather_source.standardize_record(raw)
        assert record.text == "Severe Thunderstorm Warning"

    def test_categories_include_event_severity_urgency(self, weather_source, weather_make_feature):
        record = weather_source.standardize_record(self._make_raw(weather_make_feature))
        assert "Severe Thunderstorm Warning" in record.categories
        assert "Severe" in record.categories
        assert "Immediate" in record.categories

    def test_metadata_captures_all_fields(self, weather_source, weather_make_feature):
        record = weather_source.standardize_record(self._make_raw(weather_make_feature))
        assert record.metadata["source_id"] == "alert-123"
        assert record.metadata["query_area"] == "IN"
        assert record.metadata["event"] == "Severe Thunderstorm Warning"
        assert record.metadata["severity"] == "Severe"
        assert record.metadata["urgency"] == "Immediate"
        assert record.metadata["certainty"] == "Observed"
        assert record.metadata["status"] == "Actual"
        assert record.metadata["message_type"] == "Alert"
        assert record.metadata["category"] == "Met"
        assert record.metadata["sender_name"] == "NWS Indianapolis IN"
        assert record.metadata["area_desc"] == "Marion, IN"

    def test_metadata_captures_time_fields(self, weather_source, weather_make_feature):
        record = weather_source.standardize_record(self._make_raw(weather_make_feature))
        assert record.metadata["effective_at"] == "2026-01-15T12:00:00Z"
        assert record.metadata["expires_at"] == "2026-01-15T13:00:00Z"
        assert record.metadata["ends_at"] == "2026-01-15T13:00:00Z"

    def test_raw_field_contains_full_feature(self, weather_source, weather_make_feature):
        raw = self._make_raw(weather_make_feature)
        record = weather_source.standardize_record(raw)
        assert record.raw == raw["feature"]

    def test_retrieved_at_is_set(self, weather_source, weather_make_feature):
        record = weather_source.standardize_record(self._make_raw(weather_make_feature))
        assert record.retrieved_at is not None

    def test_record_id_is_generated(self, weather_source, weather_make_feature):
        record = weather_source.standardize_record(self._make_raw(weather_make_feature))
        assert record.record_id is not None
        assert len(record.record_id) > 0

    def test_different_alerts_get_different_ids(self, weather_source, weather_make_feature):
        raw1 = self._make_raw(weather_make_feature, id="alert-1", headline="First")
        raw2 = self._make_raw(weather_make_feature, id="alert-2", headline="Second")
        record1 = weather_source.standardize_record(raw1)
        record2 = weather_source.standardize_record(raw2)
        assert record1.record_id != record2.record_id

    def test_falls_back_to_feature_id_when_props_missing_id(self, weather_source):
        raw = {
            "query_area": "IN",
            "feature": {
                "id": "fallback-feature-id",
                "properties": {
                    "headline": "Test",
                    "sent": "2026-01-15T12:00:00Z",
                },
            },
        }
        record = weather_source.standardize_record(raw)
        assert record.metadata["source_id"] == "fallback-feature-id"