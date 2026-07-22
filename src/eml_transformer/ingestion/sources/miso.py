from __future__ import annotations

import logging
from typing import Any

import requests
from bs4 import BeautifulSoup

from eml_transformer.ingestion.base import TextSource
from eml_transformer.ingestion.registry import register_source
from eml_transformer.ingestion.schema import BronzeRecord, TextRecord
from eml_transformer.utils.dates import parse_utc_datetime, utc_now
from eml_transformer.utils.stamping import stable_hash

logger = logging.getLogger(__name__)


@register_source("miso_notifications")
class MISONotificationSource(TextSource):
    name = "miso_notifications"
    source_type = "api"
    update_mode = "snapshot"
    supports_backfill = False

    def __init__(
        self,
        topic: str = "",
        take: int = 0,
        base_url: str = "https://www.misoenergy.org/api/topicnotifications/GetGroupedNotifications",
        timeout: int = 30,
    ):
        self.topic = topic
        self.take = take
        self.base_url = base_url
        self.timeout = timeout

        self.headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.misoenergy.org/markets-and-operations/notifications/",
        }

    # ------------------------------------------------------------------
    # Public pipeline interface
    # ------------------------------------------------------------------
    
    def fetch_records(
        self,
        from_date=None,
        to_date=None,
    ) -> list[dict[str, Any]]:
        """
        Public ingestion method.

        Returns source-native MISO notification records ready to write to bronze.
        """
        raw_response = self._fetch_raw()
        return self._build_bronze_records(raw_response)

    def standardize_record(
        self,
        record: BronzeRecord,
    ) -> TextRecord:
        
        raw = record.raw

        topic = raw.get("topic")
        notification = raw.get("notification", {})

        subject = notification.get("subject")
        body_html = notification.get("body") or ""

        body_text = self._html_to_text(body_html)
        url = self._build_url(notification)

        categories = [
            category
            for category in [
                "market_notice",
                topic,
            ]
            if category
        ]

        return TextRecord(
            record_id=record.record_id,
            source=record.source,
            source_type=self.source_type,
            title=subject,
            text=body_text,
            published_at=record.published_at,
            retrieved_at=record.retrieved_at,
            url=url,
            region="MISO",
            categories=categories,
            metadata={
                "topic": topic,
                "notification_id": notification.get("id"),
                "publish_date": notification.get("publishDate"),
            },
            raw=raw,
        )


    
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------


    def _fetch_raw(self) -> Any:
        """
        Download raw grouped MISO notification response.
        """
        params = {
            "topic": self.topic,
            "take": self.take,
        }

        response = requests.get(
            self.base_url,
            params=params,
            headers=self.headers,
            timeout=self.timeout,
        )

        response.raise_for_status()
        return response.json()

    def _build_bronze_records(
        self,
        raw_response: Any,
    ) -> list[BronzeRecord]:
        """Convert the grouped API response into bronze records."""
        records: list[BronzeRecord] = []
        retrieved_at = utc_now()

        for group in raw_response:
            topic = group.get("topic")

            for notification in group.get("notifications", []):
                raw = {
                    "topic": topic,
                    "notification": notification,
                }

                records.append(
                    BronzeRecord(
                        source=self.name,
                        record_id=self._make_record_id(notification),
                        published_at=self._parse_published_at(notification),
                        retrieved_at=retrieved_at,
                        raw=raw,
                    )
                )

        return records


    def _make_record_id(
        self,
        notification: dict[str, Any],
    ) -> str:
        """Return a stable, source-scoped identifier."""
        fingerprint = stable_hash(
            {
                "subject": notification.get("subject"),
                "publish_date": notification.get("publishDate"),
                "permanent_link": notification.get("permanentLinkUrl"),
            }
        )

        return f"miso:{fingerprint}"


    def _parse_published_at(
        self,
        notification: dict[str, Any],
    ):
        value = notification.get("publishDateUnformatted")

        if not value:
            return None

        return parse_utc_datetime(value)

    def _html_to_text(
        self,
        html: str,
    ) -> str:
        return BeautifulSoup(
            html,
            "html.parser",
        ).get_text(" ", strip=True)

    def _build_url(
        self,
        notification: dict[str, Any],
    ) -> str | None:
        link = notification.get("permanentLinkUrl")

        if not link:
            return None

        if link.startswith("http"):
            return link

        return f"https://www.misoenergy.org{link}"