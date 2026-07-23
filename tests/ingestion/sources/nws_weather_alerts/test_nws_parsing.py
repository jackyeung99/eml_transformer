from datetime import datetime, timezone

from eml_transformer.ingestion.schema import BronzeRecord
from eml_transformer.ingestion.sources.weather_alerts import (
    MISO_AREAS,
    WeatherAlertSource,
)


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

    def test_extracts_features_from_single_area(
        self,
        weather_source,
        weather_make_feature,
    ):
        first_feature = weather_make_feature(id="a1")
        second_feature = weather_make_feature(id="a2")

        result = weather_source._build_bronze_records(
            query_area="IN",
            raw_response={
                "features": [
                    first_feature,
                    second_feature,
                ]
            },
        )

        assert len(result) == 2
        assert all(
            isinstance(record, BronzeRecord)
            for record in result
        )
        assert result[0].record_id == "a1"
        assert result[1].record_id == "a2"

    def test_includes_query_area_in_raw_record(
        self,
        weather_source,
        weather_make_feature,
    ):
        feature = weather_make_feature(id="a1")

        result = weather_source._build_bronze_records(
            query_area="IN",
            raw_response={"features": [feature]},
        )

        assert result[0].raw["query_area"] == "IN"
        assert result[0].raw["feature"] == feature

    def test_builds_records_for_different_query_areas(
        self,
        weather_source,
        weather_make_feature,
    ):
        in_records = weather_source._build_bronze_records(
            query_area="IN",
            raw_response={
                "features": [
                    weather_make_feature(id="a1")
                ]
            },
        )
        oh_records = weather_source._build_bronze_records(
            query_area="OH",
            raw_response={
                "features": [
                    weather_make_feature(id="a2")
                ]
            },
        )

        assert in_records[0].raw["query_area"] == "IN"
        assert oh_records[0].raw["query_area"] == "OH"

    def test_handles_missing_features_key(
        self,
        weather_source,
    ):
        result = weather_source._build_bronze_records(
            query_area="IN",
            raw_response={},
        )

        assert result == []

    def test_handles_features_that_is_not_a_list(
        self,
        weather_source,
    ):
        result = weather_source._build_bronze_records(
            query_area="IN",
            raw_response={
                "features": {"id": "not-a-list"}
            },
        )

        assert result == []

    def test_falls_back_to_feature_id_when_properties_id_missing(
        self,
        weather_source,
    ):
        feature = {
            "id": "feature-id-only",
            "properties": {
                "sent": "2026-01-15T12:00:00Z",
            },
        }

        result = weather_source._build_bronze_records(
            query_area="IN",
            raw_response={"features": [feature]},
        )

        assert len(result) == 1
        assert result[0].record_id == "feature-id-only"

    def test_maps_published_at_from_sent_timestamp(
        self,
        weather_source,
        weather_make_feature,
    ):
        feature = weather_make_feature(id="a1")
        feature["properties"]["sent"] = (
            "2026-01-15T12:00:00Z"
        )

        result = weather_source._build_bronze_records(
            query_area="IN",
            raw_response={"features": [feature]},
        )

        assert result[0].published_at == datetime(
            2026,
            1,
            15,
            12,
            0,
            tzinfo=timezone.utc,
        )

    def test_uses_same_retrieved_at_for_entire_response(
        self,
        weather_source,
        weather_make_feature,
    ):
        result = weather_source._build_bronze_records(
            query_area="IN",
            raw_response={
                "features": [
                    weather_make_feature(id="a1"),
                    weather_make_feature(id="a2"),
                ]
            },
        )

        assert result[0].retrieved_at == result[1].retrieved_at
        assert result[0].retrieved_at.tzinfo is not None

    def test_skips_feature_missing_id(
        self,
        weather_source,
        weather_make_feature,
    ):
        feature = weather_make_feature(id=None)
        feature.pop("id", None)
        feature["properties"].pop("id", None)

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
        feature = weather_make_feature(id="a1")
        feature["properties"].pop("sent", None)

        result = weather_source._build_bronze_records(
            query_area="IN",
            raw_response={"features": [feature]},
        )

        assert result == []