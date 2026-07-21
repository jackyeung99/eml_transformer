from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

import eml_transformer.ingestion.sources  # noqa: F401
from eml_transformer.ingestion.registry import create_source
from eml_transformer.storage.paths import StoragePaths
from eml_transformer.storage.storage import Storage
from eml_transformer.utils.stamping import stable_hash
from eml_transformer.ingestion.base import TextSource 
from eml_transformer.utils.dates import utc_now

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
    records_failed: int = 0
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
            "failed": self.records_failed,
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
        records_failed = 0

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

            raw_records = list(
                source.fetch_records(
                    from_date=effective_from_date,
                    to_date=effective_to_date,
                )
            )
            records_fetched = len(raw_records)

            existing_hashes = self._load_seen(dedupe_key)

            bronze_rows, new_hashes, records_failed = (
                self._build_bronze_rows(
                    source=source,
                    raw_records=raw_records,
                    existing_hashes=existing_hashes,
                    run_id=run_id,
                    run_time=run_time,
                )
            )

            records_skipped = (
                records_fetched
                - len(bronze_rows)
                - records_failed
            )

            if bronze_rows:
                # Bronze data must be written before the records are marked seen.
                self.storage.append_jsonl(
                    bronze_key,
                    bronze_rows,
                )
                records_written = len(bronze_rows)

                self._save_seen(
                    key=dedupe_key,
                    seen=existing_hashes | new_hashes,
                )

            is_bounded_run = (
                from_date is not None
                or to_date is not None
            )

            should_update_checkpoint = (
                source.update_mode == "incremental"
                and update_checkpoint
                and not is_bounded_run
                and bool(raw_records)
                and records_failed == 0
            )

            if should_update_checkpoint:
                # Checkpoints are updated only after bronze and dedupe
                # persistence complete successfully.
                self._update_checkpoint(
                    source=source,
                    run_id=run_id,
                    raw_records=raw_records,
                )

            status = (
                "partial_success"
                if records_failed > 0
                else "success"
            )

            logger.info(
                (
                    "Ingestion completed | source=%s | run_id=%s "
                    "| fetched=%s | written=%s | skipped=%s | failed=%s"
                ),
                source.name,
                run_id,
                records_fetched,
                records_written,
                records_skipped,
                records_failed,
            )

            return IngestionResult(
                status=status,
                source=source.name,
                run_id=run_id,
                records_fetched=records_fetched,
                records_written=records_written,
                records_skipped=records_skipped,
                records_failed=records_failed,
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
                records_failed=records_failed,
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

        checkpoint = self._load_checkpoint(source.name)
        if checkpoint is not None:
            checkpoint_value = checkpoint.get(
                "last_checkpoint_value"
            )

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

    def _build_bronze_rows(
        self,
        source: TextSource,
        raw_records: list[dict[str, Any]],
        existing_hashes: set[str],
        run_id: str,
        run_time: datetime,
    ) -> tuple[list[dict[str, Any]], set[str], int]:
        bronze_rows: list[dict[str, Any]] = []
        new_hashes: set[str] = set()
        records_failed = 0

        for record_index, raw_record in enumerate(raw_records):
            try:
                if not isinstance(raw_record, dict):
                    raise TypeError(
                        "Raw record must be a dictionary, "
                        f"got {type(raw_record).__name__}"
                    )

                raw_hash = source.unique_id(raw_record)

                if (
                    raw_hash in existing_hashes
                    or raw_hash in new_hashes
                ):
                    continue

                bronze_rows.append(
                    {
                        "source": source.name,
                        "run_id": run_id,
                        "retrieved_at": run_time,
                        "raw_record_hash": raw_hash,
                        "raw": raw_record,
                    }
                )

                new_hashes.add(raw_hash)

            except Exception:
                records_failed += 1

                logger.warning(
                    (
                        "Skipping malformed raw record "
                        "| source=%s | record_index=%s"
                    ),
                    source.name,
                    record_index,
                    exc_info=True,
                )

        return bronze_rows, new_hashes, records_failed

    def _update_checkpoint(
        self,
        source: TextSource,
        run_id: str,
        raw_records: list[dict[str, Any]],
    ) -> None:
        checkpoint_values: list[datetime] = []

        for record_index, record in enumerate(raw_records):
            try:
                value = source.get_checkpoint_value(record)

                if value is None:
                    continue

                if not isinstance(value, datetime):
                    raise TypeError(
                        "get_checkpoint_value() must return "
                        f"datetime or None, got {type(value).__name__}"
                    )

                if value.tzinfo is None:
                    raise ValueError(
                        "Checkpoint datetime must be timezone-aware"
                    )

                checkpoint_values.append(
                    value.astimezone(timezone.utc)
                )

            except Exception:
                logger.warning(
                    (
                        "Skipping malformed checkpoint value "
                        "| source=%s | record_index=%s"
                    ),
                    source.name,
                    record_index,
                    exc_info=True,
                )

        if not checkpoint_values:
            logger.info(
                "No valid checkpoint values found | source=%s",
                source.name,
            )
            return

        last_checkpoint_value = max(checkpoint_values)

        self._save_checkpoint(
            source_name=source.name,
            checkpoint={
                "source": source.name,
                "last_successful_run_id": run_id,
                "last_checkpoint_value": last_checkpoint_value
            },
        )

        logger.info(
            "Checkpoint updated | source=%s | value=%s",
            source.name,
            last_checkpoint_value,
        )


    def _load_checkpoint(
        self,
        source_name: str,
    ) -> dict[str, Any] | None:
        checkpoint_key = self.paths.checkpoint_key(source_name)

        if not self.storage.exists(checkpoint_key):
            return None

        checkpoint = self.storage.read_json(checkpoint_key)

        if not isinstance(checkpoint, dict):
            raise TypeError(
                f"Checkpoint state for {source_name} must be a dictionary"
            )

        return checkpoint

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

        if to_date > from_date:
            raise ValueError(
                f"from_date must not be after to_date: "
                f"{from_date!r} > {to_date!r}"
            )