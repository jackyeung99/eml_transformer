from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from eml_transformer.schema.records import BronzeRecord
from eml_transformer.ingestion.results import IngestionResult
from eml_transformer.utils.dates import utc_now, parse_utc_datetime
from eml_transformer.storage.base import Storage
from eml_transformer.storage.paths import StoragePaths
from eml_transformer.logging import get_logger

logger = get_logger(__name__)

def run_incremental_ingestion(
    *,
    source: Any,
    source_name: str,
    source_config: dict[str, Any],
    storage: Storage,
    paths: StoragePaths,
    to_date: datetime | None = None,
) -> IngestionResult:
    to_date = to_date or utc_now()

    checkpoint_path = paths.checkpoint_key(source_name)
    checkpoint = storage.read_checkpoint(checkpoint_path)


    ingestion_settings = source_config.get(
        "ingestion",
        {},
    )

    lookback_days = ingestion_settings.get(
        "lookback_days",
        1,
    ) 

    from_date = resolve_incremental_start(
        checkpoint=checkpoint,
        lookback_days=lookback_days,
        to_date=to_date,
    )

    logger.info(
        "Starting incremental ingestion for %s from %s to %s",
        source_name,
        from_date.isoformat(),
        to_date.isoformat(),
    )


    result = ingest_window(
        source=source,
        source_name=source_name,
        storage=storage,
        paths=paths,
        from_date=from_date,
        to_date=to_date,
    )

    if result.status == "success":
        storage.write_checkpoint(
            checkpoint_path,
            {
                "source": source_name,
                "last_checkpoint_value": to_date,
            },
        )

    logger.info(
            (
                "Incremental ingestion completed for %s: "
                "status=%s fetched=%d written=%d skipped=%d"
            ),
            source_name,
            result.status,
            result.records_fetched,
            result.records_written,
            result.records_skipped,
        )

    return result


def resolve_incremental_start(
    *,
    checkpoint: dict[str, Any] | None,
    lookback_days: int,
    to_date: datetime,
) -> datetime:
    if lookback_days < 0:
        raise ValueError("lookback_days cannot be negative")

    checkpoint_value = (
        checkpoint.get("last_checkpoint_value")
        if checkpoint
        else None
    )

    if checkpoint_value is None:
        return to_date - timedelta(days=lookback_days)

    checkpoint_date = parse_utc_datetime(
        checkpoint_value,
    )

    return checkpoint_date - timedelta(days=lookback_days)


def ingest_window(
    *,
    source: Any,
    source_name: str,
    storage: Storage,
    paths: StoragePaths,
    from_date: datetime,
    to_date: datetime,
) -> IngestionResult:

    logger.debug(
        "Fetching %s records from %s to %s",
        source_name,
        from_date.isoformat(),
        to_date.isoformat(),
    )
      
    records: list[BronzeRecord] = source.fetch_records(
        from_date=from_date,
        to_date=to_date,
    )

    logger.debug(
        "Fetched %d records from %s",
        len(records),
        source_name,
    )

    validate_bronze_records(
        records,
        expected_source=source_name,
    )


    write_result = storage.write_bronze(
        bronze_key=paths.bronze_records(source_name),
        # Consider partitioning Bronze by ingestion date or run ID if this file becomes too large.
        dedupe_key=paths.dedupe_state(source_name),
        records=records,
    )

    logger.debug(
        "Wrote Bronze records for %s: received=%d written=%d skipped=%d",
        source_name,
        write_result.records_received,
        write_result.records_written,
        write_result.records_skipped,
    )

    return IngestionResult(
        status="success",
        source=source_name,
        reason="Ingestion completed",
        from_date=from_date,
        to_date=to_date,
        records_fetched=write_result.records_received,
        records_written=write_result.records_written,
        records_skipped=write_result.records_skipped,
    )

def validate_bronze_records(
    records: list[BronzeRecord],
    *,
    expected_source: str,
) -> None:

    missing_ids = sum(
        not record.record_id
        for record in records
    )

    if missing_ids:
        raise ValueError(
            f"Source {expected_source!r} returned "
            f"{missing_ids} record(s) without a record_id"
        )