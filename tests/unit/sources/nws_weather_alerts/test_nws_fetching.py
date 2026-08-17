from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from eml_transformer.sources.text import (
    weather_alerts as weather_module,
)

from eml_transformer.schema.records import (
    BronzeRecord,
)


UTC = timezone.utc


class FakeResponse:
    def __init__(
        self,
        payload: dict[str, Any],
    ) -> None:
        self.payload = payload

    def raise_for_status(
        self,
    ) -> None:
        return None

    def json(
        self,
    ) -> dict[str, Any]:
        return self.payload


def test_fetch_records_requests_configured_area(
    monkeypatch,
    weather_source,
    weather_make_feature,
):
    requested_urls: list[str] = []

    def fake_get(
        url: str,
        **kwargs: Any,
    ) -> FakeResponse:
        requested_urls.append(url)

        return FakeResponse(
            {
                "features": [
                    weather_make_feature(
                        id="alert-1"
                    )
                ]
            }
        )

    monkeypatch.setattr(
        weather_module.requests,
        "get",
        fake_get,
    )

    records = weather_source.fetch_records(
        from_date=datetime(
            2026,
            1,
            1,
            tzinfo=UTC,
        ),
        to_date=datetime(
            2026,
            1,
            2,
            tzinfo=UTC,
        ),
    )

    assert len(records) == 1
    assert isinstance(records[0], BronzeRecord)
    assert records[0].record_id == "alert-1"
    assert any(
        "IN" in url
        for url in requested_urls
    )


def test_fetch_records_combines_multiple_areas(
    monkeypatch,
    weather_make_feature,
):
    source = weather_module.WeatherAlertSource(
        areas=[
            "IN",
            "OH",
        ]
    )

    responses = iter(
        [
            {
                "features": [
                    weather_make_feature(
                        id="alert-in"
                    )
                ]
            },
            {
                "features": [
                    weather_make_feature(
                        id="alert-oh"
                    )
                ]
            },
        ]
    )

    monkeypatch.setattr(
        weather_module.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(
            next(responses)
        ),
    )

    records = source.fetch_records()

    assert [
        record.record_id
        for record in records
    ] == [
        "alert-in",
        "alert-oh",
    ]


def test_fetch_records_handles_empty_response(
    monkeypatch,
    weather_source,
):
    monkeypatch.setattr(
        weather_module.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(
            {
                "features": [],
            }
        ),
    )

    assert weather_source.fetch_records() == []