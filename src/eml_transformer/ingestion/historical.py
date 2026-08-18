from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterator

from tqdm.auto import tqdm

from eml_transformer.ingestion.incremental import ingest_window
from eml_transformer.ingestion.results import (
    BackfillResult,
    IngestionResult,
)
from eml_transformer.logging import silence_loggers
from eml_transformer.storage.base import Storage
from eml_transformer.storage.paths import StoragePaths

import logging

logger = logging.getLogger(__name__)

def run_historical_ingestion(
    *,
    source: Any,
    source_name: str,
    source_config: dict[str, Any],
    storage: Storage,
    paths: StoragePaths,
    from_date: datetime,
    to_date: datetime,
    window_days: int,
    seed_checkpoint: bool,
) -> BackfillResult:
    validate_historical_source(
        source=source,
        source_name=source_name,
    )

    windows = list(
        iter_date_windows(
            from_date=from_date,
            to_date=to_date,
            window_days=window_days,
        )
    )

    logger.info(
        (
            "Starting backfill for %s from %s to %s: "
            "window_days=%d windows=%d"
        ),
        source_name,
        from_date.isoformat(),
        to_date.isoformat(),
        window_days,
        len(windows),
    )

    results: list[IngestionResult] = []
    last_successful_window_end: datetime | None = None

    with tqdm(
        total=len(windows),
        desc=f"Backfill {source_name}",
        unit="window",
        dynamic_ncols=True,
    ) as progress:
        for index, (window_start, window_end) in enumerate(
            windows,
            start=1,
        ):
            progress.set_postfix(
                window=f"{window_start}→{window_end}",
                completed=f"{index - 1}/{len(windows)}",
            )

            with silence_loggers(
                "eml_transformer.ingestion.pipeline",
                "eml_transformer.ingestion",
            ):
                logger.debug(
                    (
                        "Processing backfill window %d/%d "
                        "for %s from %s to %s"
                    ),
                    index,
                    len(windows),
                    source_name,
                    window_start.isoformat(),
                    window_end.isoformat(),
                )

                result = ingest_window(
                    source=source,
                    source_name=source_name,
                    storage=storage,
                    paths=paths,
                    from_date=window_start,
                    to_date=window_end,
                )

            results.append(result)

            progress.set_postfix(
                status=result.status,
                fetched=result.records_fetched,
                written=result.records_written,
                skipped=result.records_skipped,
                completed=f"{index}/{len(windows)}",
            )
            progress.update(1)

            if result.status != "success":
                logger.error(
                    (
                        "Backfill stopped for %s after "
                        "window %d/%d failed"
                    ),
                    source_name,
                    index,
                    len(windows),
                )
                break

            last_successful_window_end = window_end

            if seed_checkpoint:
                storage.write_checkpoint(
                    paths.checkpoint_key(source_name),
                    {
                        "source": source_name,
                        "last_successful_run_id": (
                            "backfill_seed"
                        ),
                        "last_checkpoint_value": (
                            last_successful_window_end
                        ),
                    },
                )

            logger.debug(
                (
                    "Backfill window %d/%d completed for %s: "
                    "status=%s fetched=%d written=%d skipped=%d"
                ),
                index,
                len(windows),
                source_name,
                result.status,
                result.records_fetched,
                result.records_written,
                result.records_skipped,
            )

    failed_result = next(
        (
            result
            for result in results
            if result.status != "success"
        ),
        None,
    )

    status = (
        "failure"
        if failed_result is not None
        else "success"
    )

    windows_completed = sum(
        result.status == "success"
        for result in results
    )

    logger.info(
        (
            "Historical ingestion completed for %s: "
            "status=%s windows_completed=%d/%d "
            "last_successful_checkpoint=%s"
        ),
        source_name,
        status,
        windows_completed,
        len(windows),
        (
            last_successful_window_end.isoformat()
            if last_successful_window_end is not None
            else None
        ),
    )

    return summarize_historical_ingestion(
        source_name=source_name,
        from_date=from_date,
        to_date=to_date,
        window_days=window_days,
        windows_total=len(windows),
        results=results,
        status=status,
        error=(
            failed_result.error
            if failed_result is not None
            else None
        ),
    )

def validate_historical_source(
    *,
    source: Any,
    source_name: str,
) -> None:
    if source.update_mode != "incremental":
        raise ValueError(
            f"Source does not support historical ingestion "
            f"(update_mode={source.update_mode}): {source_name}"
        )

    if not source.supports_backfill:
        raise ValueError(
            f"Source explicitly disables historical ingestion: "
            f"{source_name}"
        )


def iter_date_windows(
    *,
    from_date: datetime,
    to_date: datetime,
    window_days: int,
) -> Iterator[tuple[datetime, datetime]]:
    if window_days < 1:
        raise ValueError("window_days must be at least 1")

    if from_date.tzinfo is None or to_date.tzinfo is None:
        raise ValueError(
            "Historical ingestion dates must be timezone-aware"
        )

    if from_date > to_date:
        raise ValueError(
            "from_date must be before or equal to to_date"
        )

    current = from_date
    window_size = timedelta(days=window_days)

    while current < to_date:
        window_end = min(current + window_size, to_date)

        yield current, window_end

        current = window_end


def summarize_historical_ingestion(
    *,
    source_name: str,
    from_date: datetime,
    to_date: datetime,
    window_days: int,
    windows_total: int,
    results: list[IngestionResult],
    status: str,
    error: str | None = None,
) -> BackfillResult:
    return BackfillResult(
        status=status,
        source=source_name,
        from_date=from_date,
        to_date=to_date,
        window_days=window_days,
        windows_total=windows_total,
        windows_completed=sum(
            result.status == "success"
            for result in results
        ),
        records_fetched=sum(
            result.records_fetched
            for result in results
        ),
        records_written=sum(
            result.records_written
            for result in results
        ),
        records_skipped=sum(
            result.records_skipped
            for result in results
        ),
        error=error,
    )