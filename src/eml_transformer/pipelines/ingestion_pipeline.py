from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import eml_transformer.ingestion.sources  # noqa: F401
from eml_transformer.ingestion.registry import create_source
from eml_transformer.storage.paths import StoragePaths
from eml_transformer.storage.storage import Storage
from eml_transformer.utils.stamping import stable_hash

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    status: str
    source: str
    run_id: str
    records_fetched: int
    records_written: int
    records_skipped: int = 0
    records_failed: int = 0
    bronze_key: str | None = None
    dedupe_key: str | None = None
    error: str | None = None


class IngestionPipeline:
    def __init__(self, storage: Storage, paths: StoragePaths):
        self.storage = storage
        self.paths = paths

    def run_all(
        self,
        source_configs: dict[str, dict],
    ) -> list[IngestionResult]:
        logger.info(
            "Starting ingestion for %s sources",
            len(source_configs),
        )

        results = [
            self.run_source(source_name, source_kwargs)
            for source_name, source_kwargs in source_configs.items()
        ]

        successful = sum(
            result.status == "success"
            for result in results
        )

        logger.info(
            "Ingestion complete | successful=%s/%s",
            successful,
            len(results),
        )

        return results

    def run_source(
        self,
        source_name: str,
        source_kwargs: dict[str, Any],
    ) -> IngestionResult:
        run_time = datetime.now(timezone.utc)
        run_id = run_time.strftime("%Y%m%dT%H%M%SZ")

        bronze_key: str | None = None
        dedupe_key: str | None = None

        logger.info(
            "Starting ingestion | source=%s | run_id=%s",
            source_name,
            run_id,
        )

        try:
            source = create_source(source_name, **source_kwargs)

            bronze_key = self.paths.bronze_records(source.name)
            dedupe_key = self.paths.dedupe_state(source.name)

            logger.info(
                "Fetching raw records | source=%s",
                source.name,
            )

            raw = source.fetch_raw()
            raw_records = source.parse_records(raw)

            logger.info(
                "Fetched %s records | source=%s",
                len(raw_records),
                source.name,
            )

            seen_hashes = self._load_seen(dedupe_key)

            bronze_rows = []

            for raw_record in raw_records:
                raw_hash = stable_hash(raw_record)

                if raw_hash in seen_hashes:
                    continue

                bronze_rows.append(
                    {
                        "source": source.name,
                        "run_id": run_id,
                        "retrieved_at": run_time.isoformat(),
                        "raw_record_hash": raw_hash,
                        "raw": raw_record,
                    }
                )

                seen_hashes.add(raw_hash)

            records_written = len(bronze_rows)
            records_skipped = len(raw_records) - records_written

            if bronze_rows:
                logger.info(
                    "Writing %s new bronze records | source=%s",
                    records_written,
                    source.name,
                )

                self.storage.append_jsonl(
                    bronze_rows,
                    bronze_key,
                )
            else:
                logger.info(
                    "No new bronze records to write | source=%s",
                    source.name,
                )

            self._save_seen(dedupe_key, seen_hashes)

            logger.info(
                "Finished ingestion | source=%s | fetched=%s | written=%s | skipped=%s",
                source.name,
                len(raw_records),
                records_written,
                records_skipped,
            )

            return IngestionResult(
                status="success",
                source=source.name,
                run_id=run_id,
                records_fetched=len(raw_records),
                records_written=records_written,
                records_skipped=records_skipped,
                bronze_key=bronze_key,
                dedupe_key=dedupe_key,
            )

        except Exception as e:
            logger.exception(
                "Ingestion failed | source=%s | run_id=%s",
                source_name,
                run_id,
            )

            return IngestionResult(
                status="failed",
                source=source_name,
                run_id=run_id,
                records_fetched=0,
                records_written=0,
                records_skipped=0,
                error=str(e),
                bronze_key=bronze_key,
                dedupe_key=dedupe_key,
            )

    def _load_seen(self, key: str) -> set[str]:
        if not self.storage.exists(key):
            logger.info(
                "No dedupe state found | key=%s",
                key,
            )
            return set()

        state = self.storage.read_json(key)
        seen = set(state.get("seen", []))

        logger.info(
            "Loaded dedupe state | seen=%s",
            len(seen),
        )

        return seen

    def _save_seen(self, key: str, seen: set[str]) -> None:
        self.storage.write_json(
            {
                "seen": sorted(seen),
                "count": len(seen),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            key,
        )

        logger.info(
            "Saved dedupe state | seen=%s",
            len(seen),
        )