from __future__ import annotations

from typing import Any

import pandas as pd


class FakeStorage:
    def __init__(self):
        self.data: dict[str, pd.DataFrame] = {}
        self.jsonl_data: dict[str, list[dict]] ={}

    def write_parquet(self, df: pd.DataFrame, key: str) -> None:
        self.data[key] = df.copy()

    def read_parquet(self, key: str) -> pd.DataFrame:
        if key not in self.data:
            raise FileNotFoundError(key)
        return self.data[key].copy()
    
    def write_jsonl(self, rows: list[dict], key: str) -> None:
        self.jsonl_data[key] = list(rows)

    def read_jsonl(self, key: str) -> list[dict]:
        if key not in self.jsonl_data:
            raise FileNotFoundError(key)
        return list(self.jsonl_data[key])

    def exists(self, key: str) -> bool:
        return key in self.data or key in self.jsonl_data


class FakeSource:
    def __init__(
        self,
        update_mode: str = "incremental",
        supports_backfill: bool = True,
    ):
        self.name = "gdelt"
        self.source_type = "news"
        self.update_mode = update_mode
        self.supports_backfill = supports_backfill

    def fetch_raw(self) -> pd.DataFrame:
        ...

    def parse_records(
        self,
        raw: pd.DataFrame,
    ) -> list[dict[str, Any]]:
        return raw.to_dict("records")

    def standardize_record(
        self,
        record: dict[str, Any],
    ) -> dict[str, Any]:
        ...


class FakeIngestionPipeline:
    def __init__(self, results=None):
        self.results = results or []
        self.calls = []
        self.checkpoints = []

    def run_source(
        self,
        source_name,
        source_config,
        from_date,
        to_date,
        update_checkpoint,
    ):
        self.calls.append(
            {
                "source_name": source_name,
                "source_config": source_config,
                "from_date": from_date,
                "to_date": to_date,
                "update_checkpoint": update_checkpoint,
            }
        )

        return self.results[len(self.calls) - 1]

    def initialize_checkpoint(
        self,
        source_name,
        checkpoint_value,
        run_id,
    ):
        self.checkpoints.append(
            {
                "source_name": source_name,
                "checkpoint_value": checkpoint_value,
                "run_id": run_id,
            }
        )


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
