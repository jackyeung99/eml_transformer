from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup

from eml_text_pipeline.ingestion.base import TextSource


class MISONotificationSource(TextSource):
    """
    Ingests public MISO notification data from the MISO topic notifications API.
    """

    name = "miso_notifications"
    source_type = "api"

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

    def fetch_raw(self) -> Any:
        """
        Fetch raw grouped notification JSON from MISO.
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

    def parse_records(self, raw: Any) -> pd.DataFrame:
        """
        Parse MISO grouped notification JSON into standardized records.
        """
        records = []
        retrieved_at = datetime.now(timezone.utc).isoformat()

        for group in raw:
            topic = group.get("topic")
            notifications = group.get("notifications", [])

            for notification in notifications:
                subject = notification.get("subject")
                publish_date = notification.get("publishDate")
                body_html = notification.get("body") or ""

                body_text = BeautifulSoup(
                    body_html,
                    "html.parser",
                ).get_text(" ", strip=True)

                record = {
                    "source": self.name,
                    "source_type": self.source_type,
                    "title": subject,
                    "published_at": publish_date,
                    "retrieved_at": retrieved_at,
                    "url": self._build_url(notification),
                    "raw_text": body_html,
                    "clean_text": body_text,
                }

                records.append(record)

        return pd.DataFrame(records)

    def _build_url(self, notification: dict) -> str | None:
        """
        Build a stable URL for the MISO notification if available.
        """
        link = notification.get("permanentLinkUrl")

        if not link:
            return None

        if link.startswith("http"):
            return link

        return f"https://www.misoenergy.org{link}"