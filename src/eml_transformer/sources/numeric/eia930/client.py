# sources/numeric/eia930/client.py

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class EIAClient:
    BASE_URL = "https://api.eia.gov/v2"
    MAX_PAGE_SIZE = 5_000

    def __init__(
        self,
        api_key: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_key = api_key or os.getenv("EIA_API_KEY")

        if not self.api_key:
            raise ValueError(
                "EIA API key is missing. Pass api_key or set "
                "EIA_API_KEY in the environment."
            )

        self.timeout_seconds = timeout_seconds
        self.session = self._build_session()

    @staticmethod
    def _build_session() -> requests.Session:
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

        session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "eml-transformer/1.0",
            }
        )

        session.mount(
            "https://",
            HTTPAdapter(max_retries=retries),
        )

        return session

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> EIAClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _get(
        self,
        route: str,
        *,
        params: Sequence[tuple[str, Any]] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.BASE_URL}/{route.strip('/')}/"

        query_params = [
            ("api_key", self.api_key),
            *(params or []),
        ]

        response = self.session.get(
            url,
            params=query_params,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()

        payload = response.json()

        if not isinstance(payload, dict):
            raise ValueError(
                "Expected EIA API to return a JSON object, "
                f"got {type(payload).__name__}"
            )

        if "error" in payload:
            raise RuntimeError(
                f"EIA API error: {payload['error']}"
            )

        return payload

    def get_metadata(
        self,
        route: str,
    ) -> dict[str, Any]:
        """
        Retrieve route metadata, including available frequencies,
        facets, columns, and child routes.
        """
        return self._get(route)

    def get_facet_values(
        self,
        route: str,
        facet: str,
        *,
        length: int = 5_000,
    ) -> list[dict[str, Any]]:
        """
        Retrieve valid values for a route facet.

        Examples:
            respondent -> MISO, PJM, ERCO
            type       -> D, DF, NG, TI
        """
        payload = self._get(
            f"{route.strip('/')}/facet/{facet}",
            params=[
                ("offset", 0),
                ("length", length),
            ],
        )

        response = payload.get("response", {})
        facets = response.get("facets", [])

        if not isinstance(facets, list):
            raise ValueError(
                "EIA facet response does not contain a facet list"
            )

        return facets

    def get_data_page(
        self,
        route: str,
        *,
        data: Sequence[str],
        facets: Mapping[str, Sequence[str]] | None = None,
        frequency: str | None = None,
        start: str | None = None,
        end: str | None = None,
        sort_column: str = "period",
        sort_direction: str = "asc",
        offset: int = 0,
        length: int = MAX_PAGE_SIZE,
    ) -> dict[str, Any]:
        """
        Retrieve one page of rows from an EIA data route.
        """
        if not data:
            raise ValueError(
                "At least one data column must be requested"
            )

        if not 1 <= length <= self.MAX_PAGE_SIZE:
            raise ValueError(
                f"length must be between 1 and "
                f"{self.MAX_PAGE_SIZE}"
            )

        if offset < 0:
            raise ValueError("offset cannot be negative")

        if sort_direction not in {"asc", "desc"}:
            raise ValueError(
                "sort_direction must be 'asc' or 'desc'"
            )

        params: list[tuple[str, Any]] = []

        for index, column in enumerate(data):
            params.append((f"data[{index}]", column))

        for facet_name, values in (facets or {}).items():
            for value in values:
                params.append(
                    (f"facets[{facet_name}][]", value)
                )

        if frequency is not None:
            params.append(("frequency", frequency))

        if start is not None:
            params.append(("start", start))

        if end is not None:
            params.append(("end", end))

        params.extend(
            [
                ("sort[0][column]", sort_column),
                ("sort[0][direction]", sort_direction),
                ("offset", offset),
                ("length", length),
            ]
        )

        return self._get(
            f"{route.strip('/')}/data",
            params=params,
        )

    def iter_data(
        self,
        route: str,
        *,
        data: Sequence[str],
        facets: Mapping[str, Sequence[str]] | None = None,
        frequency: str | None = None,
        start: str | None = None,
        end: str | None = None,
        sort_column: str = "period",
        sort_direction: str = "asc",
        page_size: int = MAX_PAGE_SIZE,
    ) -> Iterator[dict[str, Any]]:
        """
        Yield every row matching a query, automatically requesting
        additional pages.
        """
        offset = 0

        while True:
            payload = self.get_data_page(
                route,
                data=data,
                facets=facets,
                frequency=frequency,
                start=start,
                end=end,
                sort_column=sort_column,
                sort_direction=sort_direction,
                offset=offset,
                length=page_size,
            )

            response = payload.get("response")

            if not isinstance(response, dict):
                raise ValueError(
                    "EIA response does not contain a response object"
                )

            rows = response.get("data", [])

            if not isinstance(rows, list):
                raise ValueError(
                    "EIA response does not contain a data list"
                )

            yield from rows

            rows_received = len(rows)
            offset += rows_received

            total = int(response.get("total", 0))

            if rows_received == 0 or offset >= total:
                break