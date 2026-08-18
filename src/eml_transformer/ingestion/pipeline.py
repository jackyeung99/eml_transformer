from __future__ import annotations

import logging
from datetime import datetime

from eml_transformer.config.definitions import SourceDefinition
from eml_transformer.ingestion.historical import (
    run_historical_ingestion,
)
from eml_transformer.ingestion.incremental import (
    run_incremental_ingestion,
)
from eml_transformer.ingestion.results import (
    BackfillResult,
    IngestionResult,
)
from eml_transformer.sources.registry import create_source
from eml_transformer.storage.base import Storage
from eml_transformer.storage.paths import StoragePaths
from eml_transformer.config.loader import resolve_api_keys
logger = logging.getLogger(__name__)


class IngestionPipeline:
    def __init__(
        self,
        storage: Storage,
        paths: StoragePaths,
    ) -> None:
        self.storage = storage
        self.paths = paths

    def incremental(
        self,
        definition: SourceDefinition,
        *,
        to_date: datetime | None = None,
    ) -> IngestionResult:
        source_name = definition.name

        logger.info(
            (
                "Starting incremental ingestion pipeline "
                "for source=%s to_date=%s"
            ),
            source_name,
            (
                to_date.isoformat()
                if to_date is not None
                else "current time"
            ),
        )

        try:
            settings = resolve_api_keys(
                definition.settings,
                source_name=definition.name,
            )

            source = create_source(
                source_name,
                **definition.settings.get(
                    "ingestion",
                    {},
                ),
            )

            logger.debug(
                (
                    "Created source adapter for "
                    "source=%s adapter=%s"
                ),
                source_name,
                type(source).__name__,
            )

            result = run_incremental_ingestion(
                source=source,
                source_name=source_name,
                source_config=definition.settings,
                storage=self.storage,
                paths=self.paths,
                to_date=to_date,
            )

            logger.info(
                (
                    "Incremental ingestion pipeline completed "
                    "for source=%s: status=%s fetched=%d "
                    "written=%d skipped=%d"
                ),
                source_name,
                result.status,
                result.records_fetched,
                result.records_written,
                result.records_skipped,
            )

            return result

        except Exception as exc:
            logger.exception(
                (
                    "Incremental ingestion pipeline failed "
                    "for source=%s"
                ),
                source_name,
            )

            return IngestionResult(
                status="failure",
                source=source_name,
                reason=(
                    "Incremental ingestion raised an exception"
                ),
                error=str(exc),
            )

    def historical(
        self,
        definition: SourceDefinition,
        *,
        from_date: datetime,
        to_date: datetime,
        window_days: int = 30,
        seed_checkpoint: bool = False,
    ) -> BackfillResult:
        source_name = definition.name

        logger.info(
            (
                "Starting historical ingestion pipeline "
                "for source=%s from=%s to=%s "
                "window_days=%d seed_checkpoint=%s"
            ),
            source_name,
            from_date.isoformat(),
            to_date.isoformat(),
            window_days,
            seed_checkpoint,
        )

        try:
            source = create_source(
                source_name,
                **definition.settings.get(
                    "ingestion",
                    {},
                ),
            )

            logger.debug(
                (
                    "Created source adapter for "
                    "source=%s adapter=%s"
                ),
                source_name,
                type(source).__name__,
            )

            result = run_historical_ingestion(
                source=source,
                source_name=source_name,
                source_config=definition.settings,
                storage=self.storage,
                paths=self.paths,
                from_date=from_date,
                to_date=to_date,
                window_days=window_days,
                seed_checkpoint=seed_checkpoint,
            )

            logger.info(
                (
                    "Historical ingestion pipeline completed "
                    "for source=%s: status=%s "
                    "windows=%d/%d fetched=%d written=%d "
                    "skipped=%d failed=%d"
                ),
                source_name,
                result.status,
                result.windows_completed,
                result.windows_total,
                result.records_fetched,
                result.records_written,
                result.records_skipped,
                result.records_failed,
            )

            return result

        except Exception as exc:
            logger.exception(
                (
                    "Historical ingestion pipeline failed "
                    "for source=%s"
                ),
                source_name,
            )

            return BackfillResult(
                status="failure",
                source=source_name,
                from_date=from_date,
                to_date=to_date,
                window_days=window_days,
                windows_total=0,
                windows_completed=0,
                records_fetched=0,
                records_written=0,
                records_skipped=0,
                records_failed=0,
                error=str(exc),
            )