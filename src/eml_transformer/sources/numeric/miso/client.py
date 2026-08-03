from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, timedelta
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class MISOClient:
    BASE_URL = "https://apim.misoenergy.org/lgi/v1"

    def __init__(
        self,
        api_key: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.session = self._build_session(api_key)

    @staticmethod
    def _build_session(
        subscription_key: str | None = None,
    ) -> requests.Session:
        retries = Retry(
            total=4,
            connect=4,
            read=4,
            status=4,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
        )

        session = requests.Session()

        headers = {
            "Accept": "application/json",
            "User-Agent": "eml-transformer/1.0",
        }

        if subscription_key:
            headers["Ocp-Apim-Subscription-Key"] = subscription_key

        session.headers.update(headers)

        session.mount(
            "https://",
            HTTPAdapter(max_retries=retries),
        )

        return session

    def get(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"

        response = self.session.get(
            url,
            params=params,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()

        payload = response.json()

        if not isinstance(payload, dict):
            raise ValueError(
                f"Expected a JSON object from MISO, got "
                f"{type(payload).__name__}"
            )

        return payload

    def get_date_range(
        self,
        endpoint_template: str,
        *,
        start: date | datetime,
        end: date | datetime,
        params: dict[str, Any] | None = None,
    ) -> Iterator[tuple[date, dict[str, Any]]]:
        """
        Request every operating date from start through end, inclusive.

        endpoint_template must contain a {date} placeholder.
        """
        start_date = (
            start.date() if isinstance(start, datetime) else start
        )
        end_date = (
            end.date() if isinstance(end, datetime) else end
        )

        if start_date > end_date:
            raise ValueError("start must be on or before end")

        current_date = start_date

        while current_date <= end_date:
            endpoint = endpoint_template.format(
                date=current_date.isoformat()
            )

            yield (
                current_date,
                self.get(endpoint, params=params),
            )

            current_date += timedelta(days=1)