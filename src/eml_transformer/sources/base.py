from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Iterable

from eml_transformer.schema.records import (
    StandardizedRecord,
    BronzeRecord
)


class DataSource(ABC):
    """Shared interface for text and numeric data sources."""

    name: str
    source_type: str          # "text" or "numeric"
    # ingestion_method: str     # "api", "file", "scrape"
    update_mode: str          # "snapshot" or "incremental"
    supports_backfill: bool
    default_lookback_days: int

    @abstractmethod
    def fetch_records(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Iterable[BronzeRecord]:
        """Retrieve raw records with minimal preprocessing."""
        ...

    @abstractmethod
    def standardize_record(
        self,
        record: dict[str, Any],
    ) -> StandardizedRecord:
        """Convert one bronze raw payload into a silver record."""
        ...

    @staticmethod
    def _deduplicate_records(
        records: list[BronzeRecord], # move to iterator eventually
    ) -> list[BronzeRecord]:
        """Keep the first record for each source and record ID."""

        unique_records: list[BronzeRecord] = []
        seen_keys: set[tuple[str, str]] = set()

        for record in records:
            key = (record.source, str(record.record_id))

            if key in seen_keys:
                continue

            seen_keys.add(key)
            unique_records.append(record)

        return unique_records



    
