from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd

import eml_transformer.sources  # noqa: F401
from eml_transformer.sources.registry import create_source
from eml_transformer.storage.paths import StoragePaths
from eml_transformer.storage.storage import Storage
from eml_transformer.standardization.text_cleaning import clean_text
from eml_transformer.ingestion.schema import TextRecord, BronzeRecord

logger = logging.getLogger(__name__)

from eml_transformer.utils.profiling import profile


@dataclass
class StandardizationResult:
    status: str
    source: str

    records_read: int
    records_out: int
    records_failed: int = 0

    bronze_key: str | None = None
    silver_key: str | None = None

    error: str | None = None
    records: pd.DataFrame | None = None


    def to_summary(self) -> dict[str, object]:
        return {
            "source": self.source,
            "status": self.status,
            "read": self.records_read,
            "out": self.records_out,
            "failed": self.records_failed,
            "silver": self.silver_key,
            "error": self.error,
        }

class StandardizationPipeline:
    def __init__(
        self,
        storage: Storage,
        paths: StoragePaths,
    ):
        self.storage = storage
        self.paths = paths

    def run_all(
        self,
        source_configs: dict[str, dict],
    ) -> list[StandardizationResult]:
        logger.info(
            "Starting standardization for %s sources",
            len(source_configs),
        )

        results = [
            self.run_source(source_name, source_config)
            for source_name, source_config in source_configs.items()
        ]

        logger.info("Standardization complete")

        return results

    @profile()
    def run_source(
        self,
        source_name: str,
        source_config: dict[str, Any],
        batch_size: int = 100_000,
    ) -> StandardizationResult:
        bronze_key: str | None = None
        silver_key: str | None = None

        try:
            source = create_source(
                source_name,
                **source_config.get("standardization", {}),
            )

            bronze_key = self.paths.bronze_records(source=source.name)
            silver_key = self.paths.silver_records(source=source.name)

            if not self.storage.exists(bronze_key):
                return StandardizationResult(
                    status="skipped",
                    source=source.name,
                    records_read=0,
                    records_out=0,
                    bronze_key=bronze_key,
                    silver_key=silver_key,
                    error=f"No bronze data found for source: {source.name}",
                )

            batch: list[dict[str, Any]] = []
            seen_record_ids: set[str] = set()

            records_read = 0
            records_out = 0
            failed_records = 0
            batch_number = 0

            for row in self.storage.iter_jsonl(bronze_key):
                records_read += 1

                try:
                    bronze_record = BronzeRecord.from_dict(row)
                    result = source.standardize_record(bronze_record)

                    if result is None:
                        continue

                    standardized_records = (
                        result if isinstance(result, list) else [result]
                    )

                    for record in standardized_records:
                        record = self._clean_record(record)
                        record_dict = record.to_dict()

                        record_id = record_dict.get("record_id")

                        if record_id and record_id in seen_record_ids:
                            continue

                        if record_id:
                            seen_record_ids.add(record_id)

                        batch.append(record_dict)

                        if len(batch) >= batch_size:
                            self._write_batch(
                                records=batch,
                                source_name=source.name,
                                batch_number=batch_number,
                            )

                            records_out += len(batch)
                            batch_number += 1
                            batch.clear()

                except Exception:
                    failed_records += 1
                    logger.exception(
                        "Failed to standardize record | source=%s | row=%s",
                        source.name,
                        records_read,
                    )

            if batch:
                self._write_batch(
                    records=batch,
                    source_name=source.name,
                    batch_number=batch_number,
                )
                records_out += len(batch)

            return StandardizationResult(
                status="success",
                source=source.name,
                records_read=records_read,
                records_out=records_out,
                records_failed=failed_records,
                bronze_key=bronze_key,
                silver_key=silver_key,
            )

        except Exception as exc:
            logger.exception(
                "Standardization failed | source=%s",
                source_name,
            )

            return StandardizationResult(
                status="failed",
                source=source_name,
                records_read=0,
                records_out=0,
                error=str(exc),
                bronze_key=bronze_key,
                silver_key=silver_key,
            )
        


    def _write_batch(
        self,
        records: list[dict[str, Any]],
        source_name: str,
        batch_number: int,
    ) -> None:
        df = pd.DataFrame.from_records(records)

        df = self._deduplicate(df)

        silver_key = self.paths.silver_part(
            source=source_name,
            part=batch_number,
        )

        self.storage.write_parquet(df, silver_key)

    def _records_to_dataframe(
        self,
        records: list[TextRecord],
    ) -> pd.DataFrame:
        if not records:
            return pd.DataFrame()

        return pd.DataFrame.from_records(
            record.to_dict()
            for record in records
        )

    def _clean_record(
        self,
        record: TextRecord,
    ) -> TextRecord:
        record.title = clean_text(
            record.title or "",
        )

        record.text = clean_text(
            record.text or "",
        )

        return record

    def _deduplicate(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        if df.empty:
            return df

        if "record_id" not in df.columns:
            return df.drop_duplicates()

        return (
            df.drop_duplicates(
                subset=["record_id"],
                keep="last",
            )
            .reset_index(drop=True)
        )