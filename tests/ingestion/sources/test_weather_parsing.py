import pytest


class TestParseRecords:
    """Test the _parse_records method."""

    def test_empty_response_returns_empty_list(self, weather_source):
        assert weather_source._parse_records([]) == []

    def test_extracts_features_from_single_area(self, weather_source, weather_make_feature):
        raw = [{
            "query_area": "IN",
            "response": {
                "features": [
                    weather_make_feature(id="a1"),
                    weather_make_feature(id="a2"),
                ],
            },
        }]
        result = weather_source._parse_records(raw)
        assert len(result) == 2
        assert result[0]["query_area"] == "IN"

    def test_includes_query_area_in_each_record(self, weather_source, weather_make_feature):
        raw = [
            {
                "query_area": "IN",
                "response": {"features": [weather_make_feature(id="a1")]},
            },
            {
                "query_area": "OH",
                "response": {"features": [weather_make_feature(id="a2")]},
            },
        ]
        result = weather_source._parse_records(raw)
        assert result[0]["query_area"] == "IN"
        assert result[1]["query_area"] == "OH"

    def test_deduplicates_across_areas(self, weather_source, weather_make_feature):
        """The same alert appearing in multiple state queries should only be kept once."""
        shared_alert = weather_make_feature(id="shared-1")
        raw = [
            {"query_area": "IN", "response": {"features": [shared_alert]}},
            {"query_area": "OH", "response": {"features": [shared_alert]}},
        ]
        result = weather_source._parse_records(raw)
        assert len(result) == 1

    def test_handles_missing_features_key(self, weather_source):
        raw = [{"query_area": "IN", "response": {}}]
        assert weather_source._parse_records(raw) == []

    def test_falls_back_to_feature_id_when_no_props_id(self, weather_source):
        raw = [{
            "query_area": "IN",
            "response": {"features": [
                {"id": "feature-id-only", "properties": {}},
            ]},
        }]
        result = weather_source._parse_records(raw)
        assert len(result) == 1


class TestInit:
    """Test constructor behavior around areas."""

    def test_default_uses_miso_areas(self):
        from eml_transformer.ingestion.sources.weather_alerts import WeatherAlertSource, MISO_AREAS
        source = WeatherAlertSource()
        assert source.areas == MISO_AREAS

    def test_accepts_single_area_string(self):
        from eml_transformer.ingestion.sources.weather_alerts import WeatherAlertSource
        source = WeatherAlertSource(areas="IN")
        assert source.areas == ["IN"]

    def test_accepts_list_of_areas(self):
        from eml_transformer.ingestion.sources.weather_alerts import WeatherAlertSource
        source = WeatherAlertSource(areas=["IN", "OH"])
        assert source.areas == ["IN", "OH"]