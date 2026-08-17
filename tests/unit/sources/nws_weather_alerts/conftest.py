from __future__ import annotations

from typing import Any

import pytest

from eml_transformer.sources.text.weather_alerts import (
    WeatherAlertSource,
)


@pytest.fixture
def weather_source() -> WeatherAlertSource:
    return WeatherAlertSource(
        areas=["IN"],
    )


@pytest.fixture
def weather_make_feature():
    def make_feature(
        **property_overrides: Any,
    ) -> dict[str, Any]:
        properties = {
            "id": "alert-123",
            "@id": (
                "https://api.weather.gov/alerts/"
                "alert-123"
            ),
            "headline": (
                "Severe Thunderstorm Warning"
            ),
            "description": (
                "Damaging winds expected."
            ),
            "instruction": (
                "Take shelter immediately"
            ),
            "event": (
                "Severe Thunderstorm Warning"
            ),
            "severity": "Severe",
            "urgency": "Immediate",
            "certainty": "Observed",
            "status": "Actual",
            "messageType": "Alert",
            "category": "Met",
            "response": "Shelter",
            "sender": (
                "w-nws.webmaster@noaa.gov"
            ),
            "senderName": (
                "NWS Indianapolis IN"
            ),
            "areaDesc": "Marion, IN",
            "geocode": {
                "UGC": [
                    "INC097",
                ]
            },
            "affectedZones": [
                (
                    "https://api.weather.gov/"
                    "zones/country/INC097"
                )
            ],
            "sent": (
                "2026-01-15T12:00:00Z"
            ),
            "effective": (
                "2026-01-15T12:00:00Z"
            ),
            "expires": (
                "2026-01-15T13:00:00Z"
            ),
            "ends": (
                "2026-01-15T13:00:00Z"
            ),
        }

        properties.update(property_overrides)

        return {
            "id": properties.get("id"),
            "properties": properties,
        }

    return make_feature