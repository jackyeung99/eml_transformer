from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from time import perf_counter
from typing import Any

import eml_transformer.sources  # noqa: F401
from eml_transformer.logging import get_logger
from eml_transformer.schema.records import BronzeRecord
from eml_transformer.sources.registry import create_source
from eml_transformer.storage.base import Storage
from eml_transformer.storage.paths import StoragePaths

logger = get_logger(__name__)


@dataclass(slots=True)
class StandardizationResult:
    status: str
    source: str

    records_read: int
    records_out: int
    records_failed: int = 0

    bronze_key: str | None = None
    silver_key: str | None = None

    error: str | None = None

    def to_summary(self) -> dict[str, object]:
        return {
            "source": self.source,
            "status": self.status,
            "read": self.records_read,
            "out": self.records_out,
            "failed": self.records_failed,
            "bronze": self.bronze_key,
            "silver": self.silver_key,
            "error": self.error,
        }


class StandardizationPipeline:
    def __init__(
        self,
        storage: Storage,
        paths: StoragePaths,
    ) -> None:
        self.storage = storage
        self.paths = paths

    def run_source(
        self,
        source_name: str,
        source_config: dict[str, Any],
    ) -> StandardizationResult:
        started_at = perf_counter()

        bronze_key: str | None = None
        silver_key: str | None = None

        counters = {
            "read": 0,
            "failed": 0,
        }

        logger.info(
            "Starting standardization | source=%s",
            source_name,
        )

        try:
            stage_config = source_config.get(
                "standardization",
                {},
            )

            source_options = self._source_options(stage_config)

            source = create_source(
                source_name,
                **source_options,
            )

            output_ref = stage_config.get(
                "output",
                f"silver:{source.name}:records",
            )

            batch_size = stage_config.get(
                "batch_size",
                100_000,
            )

            write_mode = stage_config.get(
                "write_mode",
                "replace",
            )

            bronze_key = self.paths.bronze_records(
                source=source.name,
            )

            silver_key = self.paths.dataset(output_ref)

            logger.debug(
                "Resolved standardization paths "
                "| source=%s | bronze=%s | silver=%s "
                "| batch_size=%s | write_mode=%s",
                source.name,
                bronze_key,
                silver_key,
                batch_size,
                write_mode,
            )

            if not self.storage.exists(bronze_key):
                error = (
                    "No bronze data found for source: "
                    f"{source.name}"
                )

                logger.warning(
                    "Skipping standardization "
                    "| source=%s | bronze=%s | reason=%s",
                    source.name,
                    bronze_key,
                    error,
                )

                return StandardizationResult(
                    status="skipped",
                    source=source.name,
                    records_read=0,
                    records_out=0,
                    bronze_key=bronze_key,
                    silver_key=silver_key,
                    error=error,
                )

            records = self._iter_standardized_records(
                source=source,
                bronze_key=bronze_key,
                counters=counters,
            )

            records_out = self.storage.write_records(
                ref=output_ref,
                records=records,
                batch_size=batch_size,
                mode=write_mode,
            )

            elapsed_seconds = perf_counter() - started_at

            logger.info(
                "Standardization completed "
                "| source=%s | read=%s | out=%s "
                "| failed=%s | elapsed_seconds=%.2f",
                source.name,
                counters["read"],
                records_out,
                counters["failed"],
                elapsed_seconds,
            )

            return StandardizationResult(
                status="success",
                source=source.name,
                records_read=counters["read"],
                records_out=records_out,
                records_failed=counters["failed"],
                bronze_key=bronze_key,
                silver_key=silver_key,
            )

        except Exception as exc:
            elapsed_seconds = perf_counter() - started_at

            logger.exception(
                "Standardization failed "
                "| source=%s | read=%s | failed=%s "
                "| elapsed_seconds=%.2f",
                source_name,
                counters["read"],
                counters["failed"],
                elapsed_seconds,
            )

            return StandardizationResult(
                status="failure",
                source=source_name,
                records_read=counters["read"],
                records_out=0,
                records_failed=counters["failed"],
                bronze_key=bronze_key,
                silver_key=silver_key,
                error=str(exc),
            )

    def _iter_standardized_records(
        self,
        source: Any,
        bronze_key: str,
        counters: dict[str, int],
    ) -> Iterator[dict[str, Any]]:
        logger.debug(
            "Reading bronze records "
            "| source=%s | bronze=%s",
            source.name,
            bronze_key,
        )

        for row_number, row in enumerate(
            self.storage.iter_jsonl(bronze_key),
            start=1,
        ):
            counters["read"] += 1

            try:
                bronze_record = BronzeRecord.from_dict(row)

                result = source.standardize_record(
                    bronze_record,
                )

                if result is None:
                    continue

                standardized_records = (
                    result
                    if isinstance(result, (list, tuple))
                    else (result,)
                )

                for record in standardized_records:
                    yield record.to_dict()

            except Exception:
                counters["failed"] += 1

                logger.exception(
                    "Failed to standardize record "
                    "| source=%s | row=%s",
                    source.name,
                    row_number,
                )

    # def _iter_standardized_records(
    #     self,
    #     source: Any,
    #     bronze_key: str,
    #     counters: dict[str, int],
    # ) -> Iterator[dict[str, Any]]:
    #     from time import perf_counter

    #     logger.info(
    #         "Starting Bronze standardization "
    #         "| source=%s | bronze=%s",
    #         source.name,
    #         bronze_key,
    #     )

    #     rows = iter(
    #         self.storage.iter_jsonl(bronze_key)
    #     )

    #     started_at = perf_counter()
    #     last_report_at = started_at

    #     read_seconds = 0.0
    #     transform_seconds = 0.0
    #     yielded = 0
    #     skipped = 0
    #     row_number = 0

    #     try:
    #         while True:
    #             read_started_at = perf_counter()

    #             try:
    #                 row = next(rows)
    #             except StopIteration:
    #                 break

    #             read_seconds += (
    #                 perf_counter() - read_started_at
    #             )

    #             row_number += 1
    #             counters["read"] += 1

    #             transform_started_at = perf_counter()
    #             output_rows: list[dict[str, Any]] = []

    #             try:
    #                 bronze_record = BronzeRecord.from_dict(
    #                     row
    #                 )

    #                 result = source.standardize_record(
    #                     bronze_record,
    #                 )

    #                 if result is None:
    #                     skipped += 1
    #                 else:
    #                     standardized_records = (
    #                         result
    #                         if isinstance(
    #                             result,
    #                             (list, tuple),
    #                         )
    #                         else (result,)
    #                     )

    #                     output_rows = [
    #                         record.to_dict()
    #                         for record in standardized_records
    #                     ]

    #             except Exception:
    #                 counters["failed"] += 1

    #                 logger.exception(
    #                     "Failed to standardize record "
    #                     "| source=%s | row=%s",
    #                     source.name,
    #                     row_number,
    #                 )

    #             transform_seconds += (
    #                 perf_counter() - transform_started_at
    #             )

    #             yielded += len(output_rows)

    #             now = perf_counter()

    #             if (
    #                 row_number % 10_000 == 0
    #                 or now - last_report_at >= 30
    #             ):
    #                 elapsed = now - started_at
    #                 rate = (
    #                     row_number / elapsed
    #                     if elapsed
    #                     else 0.0
    #                 )

    #                 logger.info(
    #                     "Standardization progress "
    #                     "| source=%s "
    #                     "| read=%d "
    #                     "| yielded=%d "
    #                     "| skipped=%d "
    #                     "| failed=%d "
    #                     "| rate=%.0f records/s "
    #                     "| read_time=%.1fs "
    #                     "| transform_time=%.1fs "
    #                     "| elapsed=%.1fs",
    #                     source.name,
    #                     row_number,
    #                     yielded,
    #                     skipped,
    #                     counters["failed"],
    #                     rate,
    #                     read_seconds,
    #                     transform_seconds,
    #                     elapsed,
    #                 )

    #                 last_report_at = now

    #             yield from output_rows

    #     finally:
    #         elapsed = perf_counter() - started_at

    #         logger.info(
    #             "Finished Bronze standardization "
    #             "| source=%s "
    #             "| read=%,d "
    #             "| yielded=%,d "
    #             "| skipped=%,d "
    #             "| failed=%,d "
    #             "| rate=%.0f records/s "
    #             "| read_time=%.1fs "
    #             "| transform_time=%.1fs "
    #             "| elapsed=%.1fs",
    #             source.name,
    #             row_number,
    #             yielded,
    #             skipped,
    #             counters["failed"],
    #             row_number / elapsed if elapsed else 0.0,
    #             read_seconds,
    #             transform_seconds,
    #             elapsed,
    #         )

    @staticmethod
    def _source_options(
        stage_config: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Remove pipeline settings before passing configuration
        to the source constructor.

        A nested `options` mapping is preferred, but the older flat
        configuration format remains supported.
        """
        if "options" in stage_config:
            return dict(stage_config["options"])

        orchestration_keys = {
            "input",
            "output",
            "batch_size",
            "write_mode",
        }

        return {
            key: value
            for key, value in stage_config.items()
            if key not in orchestration_keys
        }