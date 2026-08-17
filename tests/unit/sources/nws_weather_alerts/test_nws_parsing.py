from __future__ import annotations

from datetime import datetime, timezone

from eml_transformer.schema.records import (
    BronzeRecord,
)


UTC = timezone.utc


def test_empty_response_returns_empty_list(
    weather_source,
):
    result = weather_source._build_bronze_records(
        query_area="IN",
        raw_response={},
    )

    assert result == []


def test_builds_bronze_records(
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

    assert len(result) == 2
    assert all(
        isinstance(record, BronzeRecord)
        for record in result
    )
    assert [
        record.record_id
        for record in result
    ] == [
        "a1",
        "a2",
    ]


def test_preserves_query_area_and_feature(
    weather_source,
    weather_make_feature,
):
    feature = weather_make_feature(id="a1")

    result = weather_source._build_bronze_records(
        query_area="IN",
        raw_response={
            "features": [
                feature,
            ]
        },
    )

    assert result[0].raw == {
        "query_area": "IN",
        "feature": feature,
    }


def test_maps_sent_to_published_at(
    weather_source,
    weather_make_feature,
):
    result = weather_source._build_bronze_records(
        query_area="IN",
        raw_response={
            "features": [
                weather_make_feature(
                    id="a1",
                    sent=(
                        "2026-01-15T12:00:00Z"
                    ),
                )
            ]
        },
    )

    assert result[0].published_at == datetime(
        2026,
        1,
        15,
        12,
        0,
        tzinfo=UTC,
    )


def test_falls_back_to_top_level_feature_id(
    weather_source,
):
    feature = {
        "id": "feature-id",
        "properties": {
            "sent": (
                "2026-01-15T12:00:00Z"
            ),
        },
    }

    result = weather_source._build_bronze_records(
        query_area="IN",
        raw_response={
            "features": [
                feature,
            ]
        },
    )

    assert len(result) == 1
    assert result[0].record_id == "feature-id"


def test_skips_invalid_features(
    weather_source,
):
    missing_id = {
        "properties": {
            "sent": (
                "2026-01-15T12:00:00Z"
            ),
        }
    }
    missing_sent = {
        "id": "alert-1",
        "properties": {
            "id": "alert-1",
        },
    }

    result = weather_source._build_bronze_records(
        query_area="IN",
        raw_response={
            "features": [
                missing_id,
                missing_sent,
            ]
        },
    )

    assert result == []


def test_ignores_non_list_features(
    weather_source,
):
    result = weather_source._build_bronze_records(
        query_area="IN",
        raw_response={
            "features": {
                "id": "not-a-list",
            }
        },
    )

    assert result == []