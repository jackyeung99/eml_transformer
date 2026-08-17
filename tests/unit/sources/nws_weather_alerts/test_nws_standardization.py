from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from eml_transformer.schema.records import (
    BronzeRecord,
    TextRecord,
)


UTC = timezone.utc

PUBLISHED_AT = datetime(
    2026,
    1,
    15,
    12,
    0,
    tzinfo=UTC,
)
RETRIEVED_AT = datetime(
    2026,
    1,
    15,
    12,
    5,
    tzinfo=UTC,
)


def make_weather_bronze_record(
    weather_make_feature,
    *,
    query_area: str = "IN",
    record_id: str = "alert-123",
    **property_overrides: Any,
) -> BronzeRecord:
    feature = weather_make_feature(
        id=record_id,
        **property_overrides,
    )

    return BronzeRecord(
        source="weather_alerts",
        record_id=record_id,
        published_at=PUBLISHED_AT,
        retrieved_at=RETRIEVED_AT,
        raw={
            "query_area": query_area,
            "feature": feature,
        },
    )


def test_returns_text_record(
    weather_source,
    weather_make_feature,
):
    bronze = make_weather_bronze_record(
        weather_make_feature
    )

    result = weather_source.standardize_record(
        bronze
    )

    assert isinstance(result, TextRecord)


def test_maps_basic_fields(
    weather_source,
    weather_make_feature,
):
    bronze = make_weather_bronze_record(
        weather_make_feature
    )

    record = weather_source.standardize_record(
        bronze
    )

    assert record.record_id == "alert-123"
    assert record.source == "weather_alerts"
    assert record.source_type == "api"
    assert record.title == (
        "Severe Thunderstorm Warning"
    )
    assert record.url == (
        "https://api.weather.gov/alerts/"
        "alert-123"
    )
    assert record.region == "IN"
    assert record.published_at == PUBLISHED_AT
    assert record.retrieved_at == RETRIEVED_AT


def test_combines_text_fields(
    weather_source,
    weather_make_feature,
):
    bronze = make_weather_bronze_record(
        weather_make_feature
    )

    record = weather_source.standardize_record(
        bronze
    )

    assert record.text == (
        "Severe Thunderstorm Warning\n\n"
        "Damaging winds expected.\n\n"
        "Take shelter immediately"
    )


def test_skips_missing_text_parts(
    weather_source,
    weather_make_feature,
):
    bronze = make_weather_bronze_record(
        weather_make_feature,
        description=None,
        instruction="",
    )

    record = weather_source.standardize_record(
        bronze
    )

    assert record.text == (
        "Severe Thunderstorm Warning"
    )
    assert "None" not in record.text


def test_builds_categories(
    weather_source,
    weather_make_feature,
):
    bronze = make_weather_bronze_record(
        weather_make_feature
    )

    record = weather_source.standardize_record(
        bronze
    )

    assert record.categories == [
        "Severe Thunderstorm Warning",
        "Severe",
        "Immediate",
    ]


def test_builds_metadata(
    weather_source,
    weather_make_feature,
):
    bronze = make_weather_bronze_record(
        weather_make_feature
    )

    record = weather_source.standardize_record(
        bronze
    )

    assert record.metadata == {
        "query_area": "IN",
        "event": (
            "Severe Thunderstorm Warning"
        ),
        "severity": "Severe",
        "urgency": "Immediate",
        "certainty": "Observed",
        "status": "Actual",
        "message_type": "Alert",
        "category": "Met",
        "response": "Shelter",
        "sender": (
            "w-nws.webmaster@noaa.gov"
        ),
        "sender_name": (
            "NWS Indianapolis IN"
        ),
        "area_desc": "Marion, IN",
        "geocode": {
            "UGC": [
                "INC097",
            ]
        },
        "affected_zones": [
            (
                "https://api.weather.gov/"
                "zones/country/INC097"
            )
        ],
        "effective_at": (
            "2026-01-15T12:00:00Z"
        ),
        "expires_at": (
            "2026-01-15T13:00:00Z"
        ),
        "ends_at": (
            "2026-01-15T13:00:00Z"
        ),
    }


def test_dimensions_default_to_empty(
    weather_source,
    weather_make_feature,
):
    bronze = make_weather_bronze_record(
        weather_make_feature
    )

    record = weather_source.standardize_record(
        bronze
    )

    assert record.dimensions == {}


def test_url_falls_back_to_feature_id(
    weather_source,
):
    bronze = BronzeRecord(
        source="weather_alerts",
        record_id="fallback-feature-id",
        published_at=PUBLISHED_AT,
        retrieved_at=RETRIEVED_AT,
        raw={
            "query_area": "IN",
            "feature": {
                "id": "fallback-feature-id",
                "properties": {
                    "headline": "Test",
                    "sent": (
                        "2026-01-15T12:00:00Z"
                    ),
                },
            },
        },
    )

    record = weather_source.standardize_record(
        bronze
    )

    assert record.record_id == (
        "fallback-feature-id"
    )
    assert record.url == "fallback-feature-id"