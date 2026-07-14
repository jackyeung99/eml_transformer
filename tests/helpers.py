from __future__ import annotations

from typing import Any

import pandas as pd
from copy import deepcopy
from datetime import datetime

class FakeStorage:
    def __init__(self):
        self.data: dict[str, pd.DataFrame] = {}
        self.jsonl_data: dict[
            str,
            list[dict[str, Any]],
        ] = {}
        self.json_data: dict[str, Any] = {}

        # Useful for verifying storage interactions.
        self.parquet_write_calls: list[
            tuple[str, pd.DataFrame]
        ] = []
        self.jsonl_write_calls: list[
            tuple[str, list[dict[str, Any]]]
        ] = []
        self.jsonl_append_calls: list[
            tuple[str, list[dict[str, Any]]]
        ] = []
        self.json_write_calls: list[
            tuple[str, Any]
        ] = []

        # Optional failure injection.
        self.write_errors: dict[str, Exception] = {}
        self.append_errors: dict[str, Exception] = {}

    def write_parquet(
        self,
        df: pd.DataFrame,
        key: str,
    ) -> None:
        self._raise_write_error(key)

        copied_df = df.copy(deep=True)

        self.data[key] = copied_df
        self.parquet_write_calls.append(
            (key, copied_df.copy(deep=True))
        )

    def read_parquet(
        self,
        key: str,
    ) -> pd.DataFrame:
        if key not in self.data:
            raise FileNotFoundError(key)

        return self.data[key].copy(deep=True)

    def write_jsonl(
        self,
        rows: list[dict[str, Any]],
        key: str,
    ) -> None:
        self._raise_write_error(key)

        copied_rows = deepcopy(rows)

        self.jsonl_data[key] = copied_rows
        self.jsonl_write_calls.append(
            (key, deepcopy(copied_rows))
        )

    def append_jsonl(
        self,
        key: str,
        rows: list[dict[str, Any]],
    ) -> None:
        """
        Append rows to an existing JSONL object.

        The argument order matches IngestionPipeline:

            storage.append_jsonl(key, rows)
        """
        if key in self.append_errors:
            raise self.append_errors[key]

        copied_rows = deepcopy(rows)

        self.jsonl_data.setdefault(key, []).extend(
            copied_rows
        )
        self.jsonl_append_calls.append(
            (key, deepcopy(copied_rows))
        )

    def read_jsonl(
        self,
        key: str,
    ) -> list[dict[str, Any]]:
        if key not in self.jsonl_data:
            raise FileNotFoundError(key)

        return deepcopy(self.jsonl_data[key])

    def write_json(
        self,
        value: Any,
        key: str,
    ) -> None:
        """
        Store checkpoint or deduplication state.

        The argument order matches IngestionPipeline:

            storage.write_json(value, key)
        """
        self._raise_write_error(key)

        copied_value = deepcopy(value)

        self.json_data[key] = copied_value
        self.json_write_calls.append(
            (key, deepcopy(copied_value))
        )

    def read_json(
        self,
        key: str,
    ) -> Any:
        if key not in self.json_data:
            raise FileNotFoundError(key)

        return deepcopy(self.json_data[key])

    def exists(
        self,
        key: str,
    ) -> bool:
        return (
            key in self.data
            or key in self.jsonl_data
            or key in self.json_data
        )

    def _raise_write_error(
        self,
        key: str,
    ) -> None:
        if key in self.write_errors:
            raise self.write_errors[key]

class FakeSource:
    def __init__(
        self,
        update_mode: str = "incremental",
        supports_backfill: bool = True,
        default_lookback_days: int = 7,
        records: list[dict[str, Any]] | None = None,
        fetch_error: Exception | None = None,
    ):
        self.name = "fake"
        self.source_type = "news"
        self.update_mode = update_mode
        self.supports_backfill = supports_backfill
        self.default_lookback_days = default_lookback_days

        self.records = (
            records if records is not None else []
        )
        self.fetch_error = fetch_error

        self.fetch_calls: list[
            dict[str, str | None]
        ] = []

    def fetch_records(
        self,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[dict[str, Any]]:
        self.fetch_calls.append(
            {
                "from_date": from_date,
                "to_date": to_date,
            }
        )

        if self.fetch_error is not None:
            raise self.fetch_error

        return self.records

    def get_checkpoint_value(
        self,
        record: dict[str, Any],
    ) -> datetime | None:
        value = record.get("published_at")

        if value is None:
            return None

        if isinstance(value, Exception):
            raise value

        if isinstance(value, datetime):
            return value

        if isinstance(value, str):
            parsed = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )

            if parsed.tzinfo is None:
                raise ValueError(
                    "Checkpoint datetime must be "
                    "timezone-aware"
                )

            return parsed

        # Returning this value allows pipeline tests to verify
        # that invalid checkpoint types are rejected.
        return value  # type: ignore[return-value]

    def fetch_raw(self) -> pd.DataFrame:
        if self.fetch_error is not None:
            raise self.fetch_error

        return pd.DataFrame(self.records)

    def parse_records(
        self,
        raw: pd.DataFrame,
    ) -> list[dict[str, Any]]:
        return raw.to_dict("records")

    def standardize_record(
        self,
        record: dict[str, Any],
    ) -> dict[str, Any]:
        return record

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
