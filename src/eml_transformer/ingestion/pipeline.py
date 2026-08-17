from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

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
        try:
            source = create_source(
                definition.name,
                **definition.settings.get("ingestion", {}),
            )

            return run_incremental_ingestion(
                source=source,
                source_name=definition.name,
                source_config=definition.settings,
                storage=self.storage,
                paths=self.paths,
                to_date=to_date,
            )

        except Exception as exc:
            logger.exception(
                "Incremental ingestion failed for %s",
                definition.name,
            )

            return IngestionResult(
                status="failure",
                source=definition.name,
                reason="Incremental ingestion raised an exception",
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
        try:
            source = create_source(
                definition.name,
                **definition.settings.get("ingestion", {}),
            )

            return run_historical_ingestion(
                source=source,
                source_name=definition.name,
                source_config=definition.settings,
                storage=self.storage,
                paths=self.paths,
                from_date=from_date,
                to_date=to_date,
                window_days=window_days,
                seed_checkpoint=seed_checkpoint,
            )

        except Exception as exc:
            logger.exception(
                "Historical ingestion failed for %s",
                definition.name,
            )

            return BackfillResult(
                status="failure",
                source=definition.name,
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