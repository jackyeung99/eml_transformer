from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from dataclasses import dataclass
from typing import Any

from tqdm.auto import tqdm


from eml_transformer.logging import silence_loggers
from eml_transformer.ingestion.registry import create_source
from eml_transformer.pipelines.ingestion_pipeline import (
    IngestionPipeline,
)

@dataclass
class BackfillResult:
    status: str
    source: str
    from_date: datetime
    to_date: datetime
    window_days: int
    windows_total: int
    windows_completed: int
    records_fetched: int
    records_written: int
    records_skipped: int
    records_failed: int = 0
    error: str | None = None

    def to_summary(self) -> dict[str, object]:
        summary = {
            "source": self.source,
            "status": self.status,
            "from": self.from_date,
            "to": self.to_date,
            "windows": f"{self.windows_completed}/{self.windows_total}",
            "fetched": self.records_fetched,
            "written": self.records_written,
            "skipped": self.records_skipped,
            "failed": self.records_failed,
        }

        if self.error:
            summary["error"] = self.error

        return summary
    
class BackfillPipeline:
    def __init__(
        self,
        ingestion_pipeline: IngestionPipeline,
    ):
        self.ingestion_pipeline = ingestion_pipeline

    def run_all(
        self,
        source_configs: dict[str, dict[str, Any]],
        from_date: datetime,
        to_date: datetime,
        window_days: int = 30,
        seed_checkpoint: bool = False,
    ) -> list[BackfillResult]:
        results = []

        for source_name, source_config in source_configs.items():
            source = create_source(
                source_name,
                **source_config.get("ingestion", {}),
            )

            if not source.supports_backfill:
                continue

            results.append(
                self.run_source(
                    source_name=source_name,
                    source_config=source_config,
                    from_date=from_date,
                    to_date=to_date,
                    window_days=window_days,
                    seed_checkpoint=seed_checkpoint,
                )
            )

        return results

    def run_source(
        self,
        source_name: str,
        source_config: dict[str, Any],
        from_date: datetime,
        to_date: datetime,
        window_days: int = 30,
        seed_checkpoint: bool = False,
    ) -> BackfillResult:
        

        source = create_source(
            source_name,
            **source_config.get('ingestion', {}),
        )

        if source.update_mode != "incremental":
            raise ValueError(
                f"Source does not support backfill "
                f"(update_mode={source.update_mode}): "
                f"{source_name}"
            )

        if not source.supports_backfill:
            raise ValueError(
                f"Source explicitly disables backfill: "
                f"{source_name}"
            )



        windows = list(
            self._iter_date_windows(
                from_date=from_date,
                to_date=to_date,
                window_days=window_days,
            )
        )


        ingestion_results = []


        with tqdm(
            total=len(windows),
            desc=f"Backfill {source_name}",
            unit="window",
            dynamic_ncols=True,
        ) as pbar:

            for window_index, (from_date, to_date) in enumerate(windows, start=1):
                pbar.set_postfix(
                    window=f"{from_date}→{to_date}",
                    completed=f"{window_index - 1}/{len(windows)}",
                )

                with silence_loggers(
                    "eml_transformer.pipelines.ingestion_pipeline",
                    "eml_transformer.ingestion",
                ):
                    result = self.ingestion_pipeline.run_source(
                        source_name=source_name,
                        source_config=source_config,
                        from_date=from_date,
                        to_date=to_date,
                        update_checkpoint=False,
                    )

                ingestion_results.append(result)

                pbar.set_postfix(
                    window=f"{from_date}→{to_date}",
                    status=result.status,
                    fetched=result.records_fetched,
                    written=result.records_written,
                    skipped=result.records_skipped,
                    completed=f"{window_index}/{len(windows)}",
                )

                pbar.update(1)
        

        failed_result = next(
            (
                result
                for result in ingestion_results
                if result.status != "success"
            ),
            None,
        )

        if failed_result:
            return self._summarize_backfill(
                source_name=source_name,
                from_date=from_date,
                to_date=to_date,
                window_days=window_days,
                windows_total=len(windows),
                ingestion_results=ingestion_results,
                status="failed",
                error=failed_result.error,
            )

        if seed_checkpoint and ingestion_results:
            final_end_date_time = windows[-1][1]

            self.ingestion_pipeline._save_checkpoint(
                source_name=source_name,
                checkpoint={
                    "source": source_name,
                    "last_successful_run_id": "backfill_seed",
                    "last_checkpoint_value": final_end_date_time,
                },
            )

        return self._summarize_backfill(
            source_name=source_name,
            from_date=from_date,
            to_date=to_date,
            window_days=window_days,
            windows_total=len(windows),
            ingestion_results=ingestion_results,
            status="success",
        )

    def _summarize_backfill(
        self,
        source_name: str,
        from_date: str,
        to_date: str,
        window_days: int,
        windows_total: int,
        ingestion_results: list[Any],
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
            windows_completed=len(ingestion_results),
            records_fetched=sum(
                result.records_fetched
                for result in ingestion_results
            ),
            records_written=sum(
                result.records_written
                for result in ingestion_results
            ),
            records_skipped=sum(
                result.records_skipped
                for result in ingestion_results
            ),
            records_failed=sum(
                getattr(result, "records_failed", 0)
                for result in ingestion_results
            ),
            error=error,
        )
    

        


    @staticmethod
    def _iter_date_windows(
        from_date: datetime,
        to_date: datetime,
        window_days: int,
    ):
        if window_days < 1:
            raise ValueError("window_days must be at least 1")

        if from_date.tzinfo is None or to_date.tzinfo is None:
            raise ValueError("Backfill dates must be timezone-aware")

        if from_date > to_date:
            raise ValueError(
                "from_date must be before or equal to to_date"
            )

        current = from_date

        while current < to_date:
            window_end = min(
                current + timedelta(days=window_days),
                to_date,
            )

            yield current, window_end
            current = window_end