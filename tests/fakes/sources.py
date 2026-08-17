from __future__ import annotations

from typing import Any
from datetime import datetime
import pandas as pd

from eml_transformer.schema.records import BronzeRecord, TextRecord


        
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
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[BronzeRecord]:
        self.fetch_calls.append(
            {
                "from_date": from_date,
                "to_date": to_date,
            }
        )

        if self.fetch_error is not None:
            raise self.fetch_error

        return self.records

    def standardize_record(
        self,
        record: BronzeRecord,
    ) -> TextRecord:
        return TextRecord(
            source=record.source,
            record_id=record.record_id,
            published_at=record.published_at,
            text=str(record.raw.get("text", "")),
            metadata={},
    )