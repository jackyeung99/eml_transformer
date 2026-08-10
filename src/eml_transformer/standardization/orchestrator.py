from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import eml_transformer.sources  # noqa: F401
from eml_transformer.schema.records import BronzeRecord
from eml_transformer.sources.registry import create_source
from eml_transformer.storage.paths import StoragePaths
from eml_transformer.storage.storage import Storage
from eml_transformer.utils.profiling import profile

logger = logging.getLogger(__name__)


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

    def run_all(
        self,
        source_configs: dict[str, dict[str, Any]],
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

    def run_source(
        self,
        source_name: str,
        source_config: dict[str, Any],
    ) -> StandardizationResult:
        bronze_key: str | None = None
        silver_key: str | None = None

        counters = {
            "read": 0,
            "failed": 0,
        }

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

            if not self.storage.exists(bronze_key):
                return StandardizationResult(
                    status="skipped",
                    source=source.name,
                    records_read=0,
                    records_out=0,
                    bronze_key=bronze_key,
                    silver_key=silver_key,
                    error=(
                        "No bronze data found for source: "
                        f"{source.name}"
                    ),
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
            logger.exception(
                "Standardization failed | source=%s",
                source_name,
            )

            return StandardizationResult(
                status="failed",
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

    @staticmethod
    def _source_options(
        stage_config: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Remove orchestration settings before passing configuration
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