from __future__ import annotations

from typing import Any

import pandas as pd


class FakeStorage:
    def __init__(self):
        self.data: dict[str, pd.DataFrame] = {}

    def write_parquet(self, df: pd.DataFrame, key: str) -> None:
        self.data[key] = df.copy()

    def read_parquet(self, key: str) -> pd.DataFrame:
        if key not in self.data:
            raise FileNotFoundError(key)
        return self.data[key].copy()

    def exists(self, key: str) -> bool:
        return key in self.data


class FakeSource:
    name = "gdelt"
    source_type = "news"

    def fetch_raw(self) -> pd.DataFrame:
        ...

    def parse_records(self, raw: pd.DataFrame) -> list[dict[str, Any]]:
        return raw.to_dict("records")

    def standardize_record(self, record: dict[str, Any]) -> dict[str, Any]:
        ...


class FakeScraper:
    def __init__(self, result: dict[str, Any] | None = None, exc: Exception | None = None):
        self.result = result or {}
        self.exc = exc
        self.urls_seen: list[str] = []

    async def scrape(self, session, url: str) -> dict[str, Any]:
        self.urls_seen.append(url)

        if self.exc:
            raise self.exc

        return self.result


class FakeEmbeddingModel:
    def __init__(self, **kwargs):
        self.calls = []
        for key, value in kwargs.items():
            setattr(self, key, value)
        

    def embed(
        self,
        texts: list[str],
        batch_size: int,
    ) -> list[list[float]]:
        self.calls.append(
            {
                "texts": texts,
                "batch_size": batch_size,
            }
        )

        return [
            [0.1, 0.2, 0.3]
            for _ in texts
        ]
