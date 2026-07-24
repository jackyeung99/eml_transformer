from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import json
import requests

from eml_transformer.ingestion.base import TextSource
from eml_transformer.ingestion.registry import register_source
from eml_transformer.ingestion.schema import BronzeRecord, TextRecord
from eml_transformer.utils.dates import parse_utc_datetime, utc_now


logger = logging.getLogger(__name__)


MISO_AREAS = [
    "IN",
    "IL",
    "MI",
    "OH",
    "KY",
    "WI",
    "MN",
    "IA",
    "MO",
    "AR",
    "LA",
    "MS",
    "ND",
    "SD",
]


class WeatherAlertParseError(ValueError):
    """Raised when a weather alert cannot become a bronze record."""


@register_source("weather_alerts")
class WeatherAlertSource(TextSource):
    """Ingest active alerts from the National Weather Service API."""

    name = "weather_alerts"
    source_type = "api"
    update_mode = "snapshot"
    supports_backfill = False

    BASE_URL = "https://api.weather.gov/alerts/active"
    REQUEST_TIMEOUT = 30

    def __init__(
        self,
        areas: list[str] | str | None = None,
        timeout: int = REQUEST_TIMEOUT,
        session: requests.Session | None = None,
    ) -> None:
        if areas is None:
            areas = MISO_AREAS

        if isinstance(areas, str):
            areas = [areas]

        self.areas = [
            area.strip().upper()
            for area in areas
            if area.strip()
        ]
        self.timeout = timeout
        self._session = session or requests.Session()

        self.headers = {
            "User-Agent": "eml-transformer-research",
            "Accept": "application/geo+json",
        }

    # ------------------------------------------------------------------
    # Public pipeline interface
    # ------------------------------------------------------------------

    def fetch_records(
        self,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[BronzeRecord]:
        """Retrieve the current active-alert snapshot."""

        if from_date is not None or to_date is not None:
            logger.debug(
                "Weather alerts ignore date bounds "
                "| from_date=%s | to_date=%s",
                from_date,
                to_date,
            )

        records: list[BronzeRecord] = []

        for area in self.areas:
            try:
                raw_response = self._fetch_area(area)
            except requests.RequestException:
                logger.warning(
                    "Failed to retrieve weather alerts | area=%s",
                    area,
                    exc_info=True,
                )
                continue

            records.extend(
                self._build_bronze_records(
                    query_area=area,
                    raw_response=raw_response,
                )
            )

        records = self._deduplicate_records(records)

        logger.info(
            "Finished weather-alert fetch | areas=%d | records=%d",
            len(self.areas),
            len(records),
        )

        return records

    def standardize_record(
        self,
        record: BronzeRecord,
    ) -> TextRecord:
        """Convert a bronze weather alert into the common text schema."""

        raw = record.raw
        query_area = raw.get("query_area")
        feature = raw.get("feature", {})
        properties = feature.get("properties", {})

        headline = properties.get("headline")
        description = properties.get("description")
        instruction = properties.get("instruction")
        event = properties.get("event")

        text = "\n\n".join(
            part
            for part in [
                headline,
                description,
                instruction,
            ]
            if isinstance(part, str) and part.strip()
        )

        categories = [
            value
            for value in [
                event,
                properties.get("severity"),
                properties.get("urgency"),
            ]
            if value
        ]

        return TextRecord(
            record_id=record.record_id,
            source=record.source,
            source_type=self.source_type,
            title=headline,
            text=text,
            published_at=record.published_at,
            retrieved_at=record.retrieved_at,
            url=(
                properties.get("@id")
                or feature.get("@id")
                or feature.get("id")
            ),
            region=query_area,
            categories=categories,
            metadata={
                "query_area": query_area,
                "event": event,
                "severity": properties.get("severity"),
                "urgency": properties.get("urgency"),
                "certainty": properties.get("certainty"),
                "status": properties.get("status"),
                "message_type": properties.get("messageType"),
                "category": properties.get("category"),
                "response": properties.get("response"),
                "sender": properties.get("sender"),
                "sender_name": properties.get("senderName"),
                "area_desc": properties.get("areaDesc"),
                "geocode": properties.get("geocode"),
                "affected_zones": properties.get("affectedZones"),
                "effective_at": properties.get("effective"),
                "expires_at": properties.get("expires"),
                "ends_at": properties.get("ends"),
            },
            raw=json.dumps(
            feature,
            default=str,
            ensure_ascii=False,
        ),
        )

    # ------------------------------------------------------------------
    # API access
    # ------------------------------------------------------------------

    def _fetch_area(
        self,
        area: str,
    ) -> dict[str, Any]:
        """Download active alerts for one state."""

        response = self._session.get(
            self.BASE_URL,
            params={"area": area},
            headers=self.headers,
            timeout=self.timeout,
        )
        response.raise_for_status()

        return response.json()

    # ------------------------------------------------------------------
    # Bronze construction
    # ------------------------------------------------------------------

    def _build_bronze_records(
        self,
        query_area: str,
        raw_response: dict[str, Any],
    ) -> list[BronzeRecord]:
        features = raw_response.get("features", [])

        if not isinstance(features, list):
            logger.warning(
                "Weather response features must be a list | area=%s",
                query_area,
            )
            return []

        retrieved_at = utc_now()
        records: list[BronzeRecord] = []

        for feature_number, feature in enumerate(features, start=1):
            try:
                record = self._build_bronze_record(
                    query_area=query_area,
                    feature=feature,
                    retrieved_at=retrieved_at,
                )
            except WeatherAlertParseError as exc:
                logger.warning(
                    "Skipping malformed weather alert "
                    "| area=%s | feature=%d | error=%s",
                    query_area,
                    feature_number,
                    exc,
                )
                continue

            records.append(record)

        return records

    def _build_bronze_record(
        self,
        query_area: str,
        feature: Any,
        retrieved_at: datetime,
    ) -> BronzeRecord:
        if not isinstance(feature, dict):
            raise WeatherAlertParseError(
                "Alert feature must be a dictionary"
            )

        properties = feature.get("properties", {})

        if not isinstance(properties, dict):
            raise WeatherAlertParseError(
                "Alert properties must be a dictionary"
            )

        record_id = properties.get("id") or feature.get("id")
        sent = properties.get("sent")

        if not record_id:
            raise WeatherAlertParseError(
                "Alert is missing its ID"
            )

        if not sent:
            raise WeatherAlertParseError(
                f"Alert {record_id!r} is missing its sent timestamp"
            )

        try:
            published_at = parse_utc_datetime(sent)
        except (TypeError, ValueError) as exc:
            raise WeatherAlertParseError(
                f"Alert {record_id!r} has an invalid sent timestamp"
            ) from exc

        return BronzeRecord(
            source=self.name,
            record_id=str(record_id),
            published_at=published_at,
            retrieved_at=retrieved_at,
            raw={
                "query_area": query_area,
                "feature": feature,
            },
        )
