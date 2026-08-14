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
from eml_transformer.storage.base import Storage

@dataclass(frozen=True)
class LocalStorage(Storage):
    paths: StoragePaths
    base_dir: Path

    def _path(self, key: str) -> Path:
        return (self.base_dir / key).resolve()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()
    
    def list(self, prefix: str) -> list[str]:
        base = self.base_dir.resolve()
        path = (base / prefix).resolve()

        if not path.exists():
            return []

        if path.is_file():
            return [prefix]

        out = []
        for p in path.rglob("*"):
            if p.is_file():
                # make both absolute → safe
                rel = p.resolve().relative_to(base)
                out.append(str(rel).replace("\\", "/"))

        return sorted(out)

    def delete_prefix(self, prefix: str) -> None:
        base = self.base_dir.resolve()
        path = (base / prefix).resolve()

        if path == base:
            raise ValueError("Refusing to delete the storage root")

        if base not in path.parents:
            raise ValueError(f"Dataset prefix escapes storage root: {prefix!r}")

        if not path.exists():
            return

        if path.is_file():
            path.unlink()
            return

        for child in sorted(path.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        path.rmdir()

    # =====================
    # Parquet
    # =====================
    def read_parquet(self, key: str) -> pd.DataFrame:
        return pd.read_parquet(
                self._path(key),
                dtype_backend="pyarrow"
                )

    def write_parquet(
        self,
        df: pd.DataFrame,
        key: str,
    ) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)

        tmp = path.with_suffix(path.suffix + ".tmp")

        df.to_parquet(
            tmp,
            engine="pyarrow",
            compression="zstd",
            index=False,
        )

        tmp.replace(path)
    

    # =====================
    # CSV
    # =====================

    def read_csv(self, key: str) -> pd.DataFrame:
        return pd.read_csv(self._path(key))


    def write_csv(
        self,
        df: pd.DataFrame,
        key: str,
        index: bool = False,
    ) -> None:
        path = self._path(key)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        tmp = path.with_suffix(
            path.suffix + ".tmp"
        )

        df.to_csv(
            tmp,
            index=index,
        )

        tmp.replace(path)
    # =====================
    # JSON
    # =====================
    def read_json(self, key: str) -> Any:
        path = self._path(key)
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def write_json(self, obj: Any, key: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, sort_keys=True, default=str)
        tmp.replace(path)

    def append_jsonl(self, key: str, rows: list[dict[str, Any]]) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists() and path.stat().st_size > 0:
            with path.open("rb+") as f:
                f.seek(-1, 2)
                last_char = f.read(1)

                if last_char != b"\n":
                    f.write(b"\n")

        with path.open("a", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False))
                f.write("\n")


    def iter_jsonl(
        self,
        key: str,
    ) -> Iterator[dict[str, Any]]:
        path = self._path(key)

        if not path.exists():
            return

        with path.open("rb") as file:
            for line in file:
                if line.strip():
                    yield json.loads(line)

    def read_jsonl(
        self,
        key: str,
    ) -> list[dict[str, Any]]:
        path = self._path(key)

        if not path.exists():
            return []

        rows = []

        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                if not line:
                    continue

                rows.append(json.loads(line))

        return rows
    
    
    # =====================
    # Pickle
    # =====================
    def read_pickle(self, key: str) -> Any:
        path = self._path(key)
        with path.open("rb") as f:
            return pickle.load(f)

    def write_pickle(self, obj: Any, key: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("wb") as f:
            pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)
        tmp.replace(path)