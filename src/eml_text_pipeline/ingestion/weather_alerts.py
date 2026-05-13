from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests

from eml_text_pipeline.ingestion.base import TextSource


class WeatherAlertSource(TextSource):
    """
    Ingest active National Weather Service alerts from weather.gov.
    """

    name = "weather_alerts"
    source_type = "api"

    def __init__(
        self,
        area: str = "IN",
        timeout: int = 30,
    ):
        self.area = area
        self.timeout = timeout

        self.base_url = (
            "https://api.weather.gov/alerts/active"
        )

        self.headers = {
            "User-Agent": (
                "eml-transformer-research "
                "jackyeung99@gmail.com"
            ),
            "Accept": "application/geo+json",
        }

    def fetch_raw(self) -> Any:
        """
        Fetch active weather alerts.
        """
        params = {
            "area": self.area,
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
        Parse weather.gov alert response into standardized records.
        """
        records = []

        retrieved_at = datetime.now(
            timezone.utc
        ).isoformat()

        features = raw.get("features", [])

        for feature in features:

            props = feature.get("properties", {})

            headline = props.get("headline")
            description = props.get("description")
            sent = props.get("sent")
            url = props.get("@id")

            severity = props.get("severity")
            urgency = props.get("urgency")
            event = props.get("event")
            area_desc = props.get("areaDesc")

            clean_text = "\n".join(
                filter(
                    None,
                    [
                        headline,
                        description,
                    ],
                )
            )

            record = {
                "source": self.name,
                "source_type": self.source_type,
                "title": headline,
                "published_at": sent,
                "retrieved_at": retrieved_at,
                "url": url,
                "raw_text": description,
                "clean_text": clean_text,
                "metadata": {
                    "event": event,
                    "severity": severity,
                    "urgency": urgency,
                    "area_desc": area_desc,
                },
            }

            records.append(record)

        return pd.DataFrame(records)