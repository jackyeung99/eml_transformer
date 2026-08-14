from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Optional, TypeVar
from collections.abc import Iterable, Iterator
from itertools import islice
import pandas as pd
import pyarrow.parquet as pq
import s3fs

import json
import joblib
import pickle
import uuid

from eml_transformer.logging import get_logger
from eml_transformer.storage.paths import DatasetRef, StoragePaths
from eml_transformer.config.loader import StorageConfig
from eml_transformer.modeling.artifacts import ModelMetadata
from eml_transformer.modeling.models.base import BaseForecastModel

logger = get_logger(__name__)

T = TypeVar("T")


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

        logger.debug(f"checking file path: {key}")
        raise NotImplementedError
    
    def list(self, prefix: str) -> list[str]:
        """
        List keys under a prefix (non-recursive or recursive depending on backend).

        Returns keys relative to storage root (same format used in read/write).
        """
        raise NotImplementedError

    def delete_prefix(self, prefix: str) -> None:
        """Delete files under one resolved dataset prefix."""
        raise NotImplementedError

    def read_parquet(self, key: str) -> pd.DataFrame:
        logger.debug(f"reading file: {key}")
        raise NotImplementedError

    def write_parquet(self, df: pd.DataFrame, key: str) -> None:
        logger.info(f"Writing {len(df)} rows to {key}")
        raise NotImplementedError

    def read_csv(self, key: str) -> pd.DataFrame:
        logger.debug(f"reading csv file: {key}")
        raise NotImplementedError

    def write_csv(
        self,
        df: pd.DataFrame,
        key: str,
        index: bool = False,
    ) -> None:
        logger.info(f"Writing {len(df)} rows to csv {key}")
        raise NotImplementedError
    

    def read_json(self, key: str) -> Any:
        logger.debug(f"reading file: {key}")
        raise NotImplementedError

    def write_json(self, obj: Any, key: str) -> None:
        logger.info(f"Writing json to {key}")
        raise NotImplementedError
    

    def read_pickle(self, key):
        logger.info(f"reading file:{key}")
        raise NotImplementedError
    
    def write_pickle(self, obj: Any, key: str):
        logger.info(f"Writing Pickle to {key}")
        raise NotImplementedError

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
    ) -> int:
        frames = (
            frame.iloc[start : start + batch_size]
            for start in range(0, len(frame), batch_size)
        )
        return self.write_batches(ref, frames, mode=mode)

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
        path: str,
    ) -> ModelMetadata | None:
        artifact_path = Path(path)
        model_path = artifact_path / "model.joblib"
        metadata_path = artifact_path / "metadata.json"

        # Only report a model as available when the complete artifact exists.
        if not model_path.exists() or not metadata_path.exists():
            return None

        with metadata_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            values = json.load(file)

        return ModelMetadata.from_dict(values)


    def read_model(
        self,
        path: str,
    ) -> tuple[BaseForecastModel, ModelMetadata]:
        artifact_path = Path(path)
        model_path = artifact_path / "model.joblib"
        metadata_path = artifact_path / "metadata.json"

        if not model_path.exists():
            raise FileNotFoundError(
                f"Model file does not exist: {model_path}"
            )

        if not metadata_path.exists():
            raise FileNotFoundError(
                f"Model metadata does not exist: {metadata_path}"
            )

        with metadata_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            metadata = ModelMetadata.from_dict(
                json.load(file)
            )

        model = joblib.load(model_path)

        if not callable(getattr(model, "predict", None)):
            raise TypeError(
                f"Loaded object from {model_path} does not implement predict()"
            )

        return model, metadata

    def _write_model_artifact(
        self,
        artifact_path: Path,
        model: BaseForecastModel,
        metadata: ModelMetadata,
    ) -> None:
        artifact_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        model_path = artifact_path / "model.joblib"
        metadata_path = artifact_path / "metadata.json"

        token = uuid.uuid4().hex

        temporary_model_path = (
            artifact_path / f".model-{token}.joblib"
        )
        temporary_metadata_path = (
            artifact_path / f".metadata-{token}.json"
        )

        try:
            joblib.dump(
                model,
                temporary_model_path,
            )

            temporary_metadata_path.write_text(
                json.dumps(
                    metadata.to_dict(),
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            temporary_model_path.replace(model_path)
            temporary_metadata_path.replace(
                metadata_path
            )

        finally:
            temporary_model_path.unlink(
                missing_ok=True
            )
            temporary_metadata_path.unlink(
                missing_ok=True
            )

    def write_model(
        self,
        path: str,
        model: BaseForecastModel,
        metadata: ModelMetadata,
    ) -> None:
        artifact_path = Path(path)

        version_path = (
            artifact_path
            / "versions"
            / metadata.model_version
        )

        if version_path.exists():
            raise FileExistsError(
                "Model version already exists: "
                f"{version_path}"
            )

        # Preserve this exact historical model and its diagnostics.
        self._write_model_artifact(
            version_path,
            model,
            metadata,
        )

        # Update the model used for current inference.
        self._write_model_artifact(
            artifact_path,
            model,
            metadata,
        )

    def read_model_metadata_history(
        self,
        path: str,
    ) -> list[ModelMetadata]:
        versions_path = Path(path) / "versions"

        if not versions_path.exists():
            return []

        history: list[ModelMetadata] = []

        for version_path in versions_path.iterdir():
            if not version_path.is_dir():
                continue

            metadata_path = (
                version_path / "metadata.json"
            )

            if not metadata_path.exists():
                continue

            with metadata_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                metadata = ModelMetadata.from_dict(
                    json.load(file)
                )

            history.append(metadata)

        return sorted(
            history,
            key=lambda item: item.trained_at,
        )

    def read_model_version(
        self,
        path: str,
        version: str,
    ) -> tuple[BaseForecastModel, ModelMetadata]:
        version_path = (
            Path(path)
            / "versions"
            / version
        )

        return self.read_model(str(version_path))


