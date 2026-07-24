from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Any

import eml_transformer.ingestion.sources  # noqa: F401
from eml_transformer.ingestion.registry import create_source
from eml_transformer.storage.paths import StoragePaths
from eml_transformer.storage.storage import Storage
from eml_transformer.ingestion.base import TextSource 
from eml_transformer.ingestion.schema import BronzeRecord
from eml_transformer.utils.dates import utc_now, parse_utc_datetime

logger = logging.getLogger(__name__)


SourceFactory = Callable[..., TextSource]
Clock = Callable[[], datetime]


@dataclass
class IngestionResult:
    status: str
    source: str
    run_id: str
    records_fetched: int
    records_written: int
    records_skipped: int = 0
    bronze_key: str | None = None
    dedupe_key: str | None = None
    error: str | None = None

    def to_summary(self) -> dict[str, object]:
        summary: dict[str, object] = {
            "source": self.source,
            "status": self.status,
            "run_id": self.run_id,
            "fetched": self.records_fetched,
            "written": self.records_written,
            "skipped": self.records_skipped,
        }

        if self.error:
            summary["error"] = self.error

        return summary


class IngestionPipeline:
    SUPPORTED_UPDATE_MODES = {"incremental", "snapshot"}

    def __init__(
        self,
        storage: Storage,
        paths: StoragePaths,
        source_factory: SourceFactory = create_source,
        clock: Clock | None = None,
    ):
        self.storage = storage
        self.paths = paths
        self.source_factory = source_factory
        self.clock = clock or utc_now

    

    def run_all(
        self,
        source_configs: Mapping[str, Mapping[str, Any]],
    ) -> list[IngestionResult]:
        """
        Run ingestion once for every configured source.

        Failures are isolated because run_source returns a failed result rather
        than raising an exception.
        """
        return [
            self.run_source(
                source_name=source_name,
                source_config=source_config,
            )
            for source_name, source_config in source_configs.items()
        ]

    def run_source(
        self,
        source_name: str,
        source_config: Mapping[str, Any],
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        update_checkpoint: bool = True,
    ) -> IngestionResult:
        """
        Fetch and persist raw records for one source.

        Passing either from_date or to_date makes the run a bounded/manual run.
        Bounded runs never update the normal incremental checkpoint.
        """
        run_time = self._get_run_time()
        run_id = self._make_run_id(run_time)

        result_source_name = source_name
        bronze_key: str | None = None
        dedupe_key: str | None = None

        records_fetched = 0
        records_written = 0
        records_skipped = 0

        try:
            self._validate_date_range(
                from_date=from_date,
                to_date=to_date,
            )

            source = self._create_source(
                source_name=source_name,
                source_config=source_config,
            )

            result_source_name = source.name

            self._validate_source(source)

            bronze_key = self.paths.bronze_records(source.name)
            dedupe_key = self.paths.dedupe_state(source.name)

            effective_from_date = self._resolve_from_date(
                source=source,
                requested_from_date=from_date,
                run_time=run_time,
            ) # should be datetime 

            effective_to_date = self._resolve_to_date(
                source=source,
                requested_to_date=to_date,
                run_time=run_time,
            ) # should be datetime 

            logger.info(
                (
                    "Fetching raw records | source=%s | update_mode=%s "
                    "| from=%s | to=%s"
                ),
                source.name,
                source.update_mode,
                effective_from_date,
                effective_to_date,
            )

            records = source.fetch_records(
                from_date=effective_from_date,
                to_date=effective_to_date,
            )

            records_fetched = len(records)
            existing_ids = self._load_seen(dedupe_key)


            self._validate_source_output(source, records)

            # dedupe 
            new_records, new_ids = self._filter_new_records(
                records,
                existing_ids,
            )

            records_skipped = (
                records_fetched
                - len(new_records)
            )

            if new_records:
                # Bronze data must be written before the records are marked seen.
                self.storage.append_jsonl(
                    bronze_key,
                    [record.to_dict() for record in new_records],
                )

                records_written = len(new_records)

                self._save_seen(
                    key=dedupe_key,
                    seen=existing_ids | new_ids,
                )

            is_bounded_run = (
                from_date is not None
                or to_date is not None
            )

            should_update_checkpoint = (
                source.update_mode == "incremental"
                and update_checkpoint
                and not is_bounded_run
                and bool(records)
            )

            if should_update_checkpoint:
                # Checkpoints are updated only after bronze and dedupe
                # persistence complete successfully.
                self._update_checkpoint(
                    source_name=source.name,
                    run_id=run_id,
                    records=records,
                )


            logger.info(
                (
                    "Ingestion completed | source=%s | run_id=%s "
                    "| fetched=%s | written=%s | skipped=%s"
                ),
                source.name,
                run_id,
                records_fetched,
                records_written,
                records_skipped,
            )

            return IngestionResult(
                status="success",
                source=source.name,
                run_id=run_id,
                records_fetched=records_fetched,
                records_written=records_written,
                records_skipped=records_skipped,
                bronze_key=bronze_key,
                dedupe_key=dedupe_key,
            )

        except Exception as exc:
            logger.exception(
                "Ingestion failed | source=%s | run_id=%s",
                result_source_name,
                run_id,
            )

            return IngestionResult(
                status="failed",
                source=result_source_name,
                run_id=run_id,
                records_fetched=records_fetched,
                records_written=records_written,
                records_skipped=records_skipped,
                error=str(exc),
                bronze_key=bronze_key,
                dedupe_key=dedupe_key,
            )

    def _create_source(
        self,
        source_name: str,
        source_config: Mapping[str, Any],
    ) -> TextSource:
        ingestion_config = source_config.get("ingestion", {})

        if not isinstance(ingestion_config, Mapping):
            raise TypeError(
                f"Ingestion configuration for {source_name!r} "
                "must be a mapping"
            )

        return self.source_factory(
            source_name,
            **dict(ingestion_config),
        )


    def _validate_source(
        self,
        source: TextSource,
    ) -> None:
        if not source.name:
            raise ValueError("Source name must not be empty")

        if source.update_mode not in self.SUPPORTED_UPDATE_MODES:
            raise ValueError(
                f"Unsupported update mode for {source.name}: "
                f"{source.update_mode!r}"
            )

        if source.update_mode == "incremental":
            lookback_days = getattr(
                source,
                "default_lookback_days",
                1,
            )

            if not isinstance(lookback_days, int):
                raise TypeError(
                    f"default_lookback_days for {source.name} "
                    "must be an integer"
                )

            if lookback_days < 0:
                raise ValueError(
                    f"default_lookback_days for {source.name} "
                    "must not be negative"
                )
    
    def _resolve_to_date(
        self,
        source: TextSource,
        requested_to_date: datetime | None,
        run_time: datetime,
    ) -> datetime | None:
        if requested_to_date is not None:
            return requested_to_date

        if source.update_mode == "incremental":
            return run_time

        return None


    def _resolve_from_date(
        self,
        source: TextSource,
        requested_from_date: datetime | None,
        run_time: datetime,
    ) -> datetime | None:
        if source.update_mode != "incremental":  
            return None
            
        if requested_from_date is not None:
            return requested_from_date

        checkpoint_value = self._load_checkpoint(source.name)
        

        if checkpoint_value is not None:
            return checkpoint_value

        lookback_days = getattr(
            source,
            "default_lookback_days",
            1,
        )

        return (
            run_time - timedelta(days=lookback_days)
        )

   

    def _update_checkpoint(
        self,
        source_name: str,
        run_id: str,
        records: list[BronzeRecord],
    ) -> None:
        checkpoint_values = [
            record.published_at.astimezone(timezone.utc)
            for record in records
            if record.published_at is not None
        ]

        if not checkpoint_values:
            logger.info(
                "No checkpoint values found | source=%s",
                source_name,
            )
            return

        last_checkpoint_value = max(checkpoint_values)

        self._save_checkpoint(
            source_name=source_name,
            checkpoint={
                "source": source_name,
                "last_successful_run_id": run_id,
                "last_checkpoint_value": last_checkpoint_value,
            },
        )

        logger.info(
            "Checkpoint updated | source=%s | value=%s",
            source_name,
            last_checkpoint_value.isoformat(),
        )

    def _load_checkpoint(
        self,
        source_name: str,
    ) -> datetime | None:
        key = self.paths.checkpoint_key(source_name)

        if not self.storage.exists(key):
            return None

        checkpoint = self.storage.read_json(key)

        value = checkpoint.get("last_checkpoint_value")
        if value is None:
            return None

        return parse_utc_datetime(value)

    def _save_checkpoint(
        self,
        source_name: str,
        checkpoint: Mapping[str, Any],
    ) -> None:
        checkpoint_key = self.paths.checkpoint_key(source_name)

        payload = {
            **checkpoint,
            "updated_at": self._get_run_time(),
        }

        self.storage.write_json(
            payload,
            checkpoint_key,
        )

    def _load_seen(
        self,
        key: str,
    ) -> set[str]:
        if not self.storage.exists(key):
            return set()

        state = self.storage.read_json(key)

        if not isinstance(state, dict):
            raise TypeError(
                f"Deduplication state at {key!r} must be a dictionary"
            )

        seen = state.get("seen", [])

        if not isinstance(seen, list):
            raise TypeError(
                f"Deduplication field 'seen' at {key!r} "
                "must be a list"
            )

        if not all(isinstance(value, str) for value in seen):
            raise TypeError(
                f"Deduplication state at {key!r} "
                "must contain only string hashes"
            )

        return set(seen)

    def _save_seen(
        self,
        key: str,
        seen: set[str],
    ) -> None:
        self.storage.write_json(
            {
                "seen": sorted(seen),
                "count": len(seen),
                "updated_at": self._get_run_time(),
            },
            key,
        )


    def _get_run_time(self) -> datetime:
        value = self.clock()

        if not isinstance(value, datetime):
            raise TypeError("Clock must return a datetime")

        if value.tzinfo is None:
            raise ValueError(
                "Clock must return a timezone-aware datetime"
            )

        return value.astimezone(timezone.utc)
    
    @staticmethod
    def _filter_new_records(
        records: list[BronzeRecord],
        existing_ids: set[str],
    ) -> tuple[list[BronzeRecord], set[str]]:
        new_records: list[BronzeRecord] = []
        new_ids: set[str] = set()

        for record in records:
            record_id = record.record_id

            if record_id in existing_ids or record_id in new_ids:
                continue

            new_records.append(record)
            new_ids.add(record_id)

        return new_records, new_ids

    @staticmethod
    def _validate_source_output(
        source: TextSource,
        records: list[BronzeRecord],
    ) -> None:
        if not isinstance(records, list):
            raise TypeError("fetch_records() must return a list")

        for index, record in enumerate(records):
            if not isinstance(record, BronzeRecord):
                raise TypeError(
                    f"{source.name}.fetch_records() returned "
                    f"{type(record).__name__} at index {index}; "
                    "expected BronzeRecord"
                )

            if record.source != source.name:
                raise ValueError(
                    f"Record source {record.source!r} does not match "
                    f"{source.name!r}"
                )

            if not record.record_id.strip():
                raise ValueError("source_record_id cannot be empty")

            if (
                record.published_at is not None
                and record.published_at.tzinfo is None
            ):
                raise ValueError("published_at must be timezone-aware")

            if record.retrieved_at.tzinfo is None:
                raise ValueError("retrieved_at must be timezone-aware")

            if not isinstance(record.raw, dict):
                raise TypeError("raw must be a dictionary")

    @staticmethod
    def _make_run_id(run_time: datetime) -> str:
        return run_time.strftime("%Y%m%dT%H%M%S")


    @staticmethod
    def _validate_date_range(
        from_date: datetime | None,
        to_date: datetime | None,
    ) -> None:
        """
        Validate ordering when both values are ISO date or datetime strings.

        Individual sources may perform stricter validation based on the API
        format they require.
        """
        if from_date is None or to_date is None:
            return

        if from_date > to_date:
            raise ValueError(
                f"from_date must not be after to_date: "
                f"{from_date!r} > {to_date!r}"
            )