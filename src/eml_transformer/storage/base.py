from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from itertools import islice
from pathlib import Path, PurePosixPath
from typing import Any, TypeVar

import joblib
import pandas as pd

from eml_transformer.logging import get_logger
from eml_transformer.modeling.artifacts import ModelMetadata
from eml_transformer.modeling.models.base import BaseForecastModel
from eml_transformer.storage.paths import DatasetRef, StoragePaths
from eml_transformer.schema.records import BronzeRecord
from eml_transformer.utils.dates import utc_now


logger = get_logger(__name__)

T = TypeVar("T")


@dataclass(frozen=True)
class BronzeWriteResult:
    """Counts produced by a deduplicated bronze append."""

    records_received: int
    records_written: int
    records_skipped: int


def batched(values: Iterable[T], size: int) -> Iterator[list[T]]:
    """Lazily collect values into bounded in-memory batches."""
    if size <= 0:
        raise ValueError("Batch size must be greater than zero")

    iterator = iter(values)

    while batch := list(islice(iterator, size)):
        yield batch


class Storage:
    paths: StoragePaths

    def exists(self, key: str) -> bool:
        logger.debug("Checking file path: %s", key)
        raise NotImplementedError

    def list(self, prefix: str) -> list[str]:
        """List keys beneath a prefix relative to the storage root."""
        raise NotImplementedError

    def delete_prefix(self, prefix: str) -> None:
        """Delete files under one resolved dataset prefix."""
        raise NotImplementedError

    def read_parquet(self, key: str) -> pd.DataFrame:
        logger.debug("Reading Parquet file: %s", key)
        raise NotImplementedError

    def write_parquet(self, df: pd.DataFrame, key: str) -> None:
        logger.info("Writing %s rows to %s", len(df), key)
        raise NotImplementedError

    def read_csv(self, key: str) -> pd.DataFrame:
        logger.debug("Reading CSV file: %s", key)
        raise NotImplementedError

    def write_csv(
        self,
        df: pd.DataFrame,
        key: str,
        index: bool = False,
    ) -> None:
        logger.info("Writing %s rows to CSV %s", len(df), key)
        raise NotImplementedError

    def read_json(self, key: str) -> Any:
        logger.debug("Reading JSON file: %s", key)
        raise NotImplementedError

    def write_json(self, obj: Any, key: str) -> None:
        logger.info("Writing JSON file: %s", key)
        raise NotImplementedError

    def iter_jsonl(
        self,
        key: str,
    ) -> Iterator[dict[str, Any]]:
        """Yield JSON objects from a JSONL file."""
        raise NotImplementedError

    def append_jsonl(
        self,
        key: str,
        records: Iterable[dict[str, Any]],
    ) -> None:
        """Append JSON records using the active storage backend."""
        raise NotImplementedError
    

    def read_pickle(self, key: str) -> Any:
        logger.debug("Reading pickle file: %s", key)
        raise NotImplementedError

    def write_pickle(self, obj: Any, key: str) -> None:
        logger.info("Writing pickle file: %s", key)
        raise NotImplementedError

    # =====================
    # Ingestion artifacts
    # =====================
    def read_checkpoint(self, key: str) -> dict[str, Any] | None:
        """Read an ingestion checkpoint, returning None when absent."""
        if not self.exists(key):
            return None

        checkpoint = self.read_json(key)
        if not isinstance(checkpoint, dict):
            raise TypeError(
                f"Checkpoint at {key!r} must contain a JSON object"
            )

        return checkpoint

    def write_checkpoint(
        self,
        key: str,
        checkpoint: dict[str, Any],
    ) -> None:
        """Persist an ingestion checkpoint."""
        self.write_json(checkpoint, key)

    def read_seen_ids(self, key: str) -> set[str]:
        """Read identifiers already persisted for a bronze dataset."""
        if not self.exists(key):
            return set()

        data = self.read_json(key)

        # Backward compatibility with the previous list-only format.
        if isinstance(data, list):
            values = data
        elif isinstance(data, dict):
            values = data.get("seen", [])
        else:
            raise TypeError(
                f"Seen-ID index at {key!r} must contain a JSON object"
            )

        if not isinstance(values, list):
            raise TypeError(
                f"Seen-ID index field 'seen' at {key!r} "
                "must contain a JSON array"
            )

        return {str(value) for value in values}

    def write_seen_ids(self, key: str, seen_ids: set[str]) -> None:
        """Persist deduplication identifiers in deterministic order."""
        self.write_json(
            {
                "seen": sorted(seen_ids),
                "updated_at": utc_now().isoformat(),
                "count": len(seen_ids),
            },
            key,
        )

    def write_bronze(
        self,
        *,
        bronze_key: str,
        dedupe_key: str,
        records: list[BronzeRecord],
    ) -> BronzeWriteResult:
        """Append unseen bronze records and update the dedupe index."""
        existing_ids = self.read_seen_ids(dedupe_key)

        new_records: list[BronzeRecord] = []
        new_ids: set[str] = set()

        for record in records:
            if (
                record.record_id in existing_ids
                or record.record_id in new_ids
            ):
                continue

            new_records.append(record)
            new_ids.add(record.record_id)

        if new_records:
            # Write data before marking identifiers as seen.
            self.append_jsonl(
                bronze_key,
                [
                    record.to_dict()
                    for record in new_records
                ],
            )

            self.write_seen_ids(
                dedupe_key,
                existing_ids | new_ids,
            )

        return BronzeWriteResult(
            records_received=len(records),
            records_written=len(new_records),
            records_skipped=(
                len(records) - len(new_records)
            ),
        )

    # =====================
    # Dataset batching
    # =====================
    def read_batches(
        self,
        ref: DatasetRef | str,
    ) -> Iterator[pd.DataFrame]:
        """Yield one Parquet part at a time without loading the dataset."""
        prefix = self.paths.dataset(ref)

        for key in self.list(prefix):
            name = PurePosixPath(key).name
            if name.startswith("part-") and name.endswith(".parquet"):
                yield self.read_parquet(key)

    def read_dataset(
        self,
        ref: DatasetRef | str,
    ) -> pd.DataFrame:
        """Explicitly load a complete dataset for global operations."""
        batches = self.read_batches(ref)

        try:
            return pd.concat(batches, ignore_index=True)
        except ValueError:
            return pd.DataFrame()

    def write_batches(
        self,
        ref: DatasetRef | str,
        batches: Iterable[pd.DataFrame],
        *,
        mode: str = "replace",
    ) -> int:
        """Write DataFrames lazily as numbered Parquet parts."""
        if mode not in {"replace", "append"}:
            raise ValueError(f"Unsupported write mode: {mode!r}")

        if mode == "replace":
            self.delete_prefix(self.paths.dataset(ref))
            part_number = 0
        else:
            part_number = self.next_part_number(ref)

        records_written = 0

        for frame in batches:
            if frame.empty:
                continue

            key = self.paths.part(ref, part_number)
            self.write_parquet(frame, key)
            records_written += len(frame)
            part_number += 1

        return records_written

    def write_records(
        self,
        ref: DatasetRef | str,
        records: Iterable[dict[str, Any]],
        *,
        batch_size: int = 100_000,
        mode: str = "replace",
    ) -> int:
        """Lazily convert records to bounded DataFrames and write them."""
        frames = (
            pd.DataFrame.from_records(record_batch)
            for record_batch in batched(records, batch_size)
        )
        return self.write_batches(ref, frames, mode=mode)

    def write_dataframe(
        self,
        ref: DatasetRef | str,
        frame: pd.DataFrame,
        *,
        batch_size: int = 100_000,
        mode: str = "replace",
        dedupe_columns: Iterable[str] | None = None,
        keep: str | bool = "last",
    ) -> int:
        """Write a DataFrame in bounded parts with optional deduplication."""
        if batch_size <= 0:
            raise ValueError("Batch size must be greater than zero")

        if dedupe_columns is not None:
            columns = list(dedupe_columns)

            missing = [
                column
                for column in columns
                if column not in frame.columns
            ]
            if missing:
                raise ValueError(
                    f"Cannot deduplicate dataset {ref!r}; "
                    f"missing columns: {missing}"
                )

            frame = frame.drop_duplicates(
                subset=columns,
                keep=keep,
            )

        frames = (
            frame.iloc[start : start + batch_size]
            for start in range(0, len(frame), batch_size)
        )

        return self.write_batches(
            ref,
            frames,
            mode=mode,
        )
    
    def next_part_number(self, ref: DatasetRef | str) -> int:
        prefix = self.paths.dataset(ref)
        numbers: list[int] = []

        for key in self.list(prefix):
            stem = PurePosixPath(key).stem
            if not stem.startswith("part-"):
                continue
            try:
                numbers.append(int(stem.removeprefix("part-")))
            except ValueError:
                continue

        return max(numbers, default=-1) + 1

    # =====================
    # Model Archiving
    # =====================

    
    def read_model_metadata(
        self,
        name: str,
    ) -> ModelMetadata | None:
        model_key = self.paths.model_file(name)
        metadata_key = self.paths.model_metadata(name)

        # Only report the model as available when both
        # required artifacts exist.
        if (
            not self.exists(model_key)
            or not self.exists(metadata_key)
        ):
            return None

        values = self.read_json(metadata_key)

        return ModelMetadata.from_dict(values)


    def read_model(
        self,
        name: str,
    ) -> tuple[
        BaseForecastModel,
        ModelMetadata,
    ]:
        model_key = self.paths.model_file(name)
        metadata_key = self.paths.model_metadata(name)

        if not self.exists(model_key):
            raise FileNotFoundError(
                f"Model file does not exist: {model_key}"
            )

        if not self.exists(metadata_key):
            raise FileNotFoundError(
                "Model metadata does not exist: "
                f"{metadata_key}"
            )

        metadata = ModelMetadata.from_dict(
            self.read_json(metadata_key)
        )

        model = self.read_pickle(model_key)

        if not callable(
            getattr(model, "forecast", None)
        ):
            raise TypeError(
                f"Loaded object from {model_key} "
                "does not implement forecast()"
            )

        return model, metadata


    def _write_model_artifact(
        self,
        *,
        model_key: str,
        metadata_key: str,
        model: BaseForecastModel,
        metadata: ModelMetadata,
    ) -> None:
        self.write_pickle(
            model,
            model_key,
        )

        self.write_json(
            metadata.to_dict(),
            metadata_key,
        )


    def write_model(
        self,
        name: str,
        model: BaseForecastModel,
        metadata: ModelMetadata,
    ) -> None:
        version_model_key = (
            self.paths.model_version_file(
                name,
                metadata.model_version,
            )
        )

        version_metadata_key = (
            self.paths.model_version_metadata(
                name,
                metadata.model_version,
            )
        )

        if (
            self.exists(version_model_key)
            or self.exists(version_metadata_key)
        ):
            raise FileExistsError(
                "Model version already exists: "
                f"{self.paths.model_version(name, metadata.model_version)}"
            )

        # Preserve the immutable historical version.
        self._write_model_artifact(
            model_key=version_model_key,
            metadata_key=version_metadata_key,
            model=model,
            metadata=metadata,
        )

        # Update the artifacts used for current inference.
        self._write_model_artifact(
            model_key=self.paths.model_file(name),
            metadata_key=(
                self.paths.model_metadata(name)
            ),
            model=model,
            metadata=metadata,
        )


    def read_model_metadata_history(
        self,
        name: str,
    ) -> list[ModelMetadata]:
        versions_prefix = self.paths.model_versions(
            name
        )

        metadata_keys = [
            key
            for key in self.list(versions_prefix)
            if key.endswith("/metadata.json")
        ]

        history: list[ModelMetadata] = []

        for metadata_key in metadata_keys:
            values = self.read_json(metadata_key)

            history.append(
                ModelMetadata.from_dict(values)
            )

        return sorted(
            history,
            key=lambda item: item.trained_at,
        )


    def read_model_version(
        self,
        name: str,
        version: str,
    ) -> tuple[
        BaseForecastModel,
        ModelMetadata,
    ]:
        model_key = self.paths.model_version_file(
            name,
            version,
        )

        metadata_key = (
            self.paths.model_version_metadata(
                name,
                version,
            )
        )

        if not self.exists(model_key):
            raise FileNotFoundError(
                "Model version file does not exist: "
                f"{model_key}"
            )

        if not self.exists(metadata_key):
            raise FileNotFoundError(
                "Model version metadata does not exist: "
                f"{metadata_key}"
            )

        metadata = ModelMetadata.from_dict(
            self.read_json(metadata_key)
        )

        model = self.read_pickle(model_key)

        if not callable(
            getattr(model, "forecast", None)
        ):
            raise TypeError(
                f"Loaded object from {model_key} "
                "does not implement forecast()"
            )

        return model, metadata

    def write_forecasts(
        self,
        ref: DatasetRef | str,
        forecasts: pd.DataFrame,
        *,
        batch_size: int = 100_000,
    ) -> int:
        if forecasts.empty:
            return 0

        existing = self.read_dataset(ref)

        if existing.empty:
            combined = forecasts.copy()
        else:
            _validate_matching_columns(
                existing,
                forecasts,
            )

            combined = pd.concat(
                [existing, forecasts],
                ignore_index=True,
            )

        combined = combined.drop_duplicates(
            subset=["forecast_id"],
            keep="last",
        )

        return self.write_dataframe(
            ref,
            combined,
            batch_size=batch_size,
            mode="replace",
        )



def _validate_matching_columns(
    existing: pd.DataFrame,
    incoming: pd.DataFrame,
) -> None:
    existing_columns = list(existing.columns)
    incoming_columns = list(incoming.columns)

    if existing_columns != incoming_columns:
        raise ValueError(
            "Appended DataFrame columns do not match "
            "the existing dataset. "
            f"Expected {existing_columns!r}, "
            f"received {incoming_columns!r}"
        )