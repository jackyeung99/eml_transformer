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


@dataclass
class S3Storage(Storage):
    """
    S3-backed storage using s3fs/fsspec under the hood.

    - key is a path relative to (bucket, prefix)
      e.g. key="data/bronze/equities.parquet"
    - best-effort "atomic" write:
        write to temp key -> copy to final -> delete temp
      (S3 doesn't support true atomic rename)
    """
    paths: StoragePaths
    bucket: str
    prefix: str = ""

    # credential/config controls (optional)
    region: Optional[str] = None
    profile: Optional[str] = None
    endpoint_url: Optional[str] = None  # for MinIO/localstack if needed

    # internal cached fs (don’t pass in init)
    _fs: Any = field(init=False, repr=False, default=None)

    def _init_fs(self):
        if self._fs is not None:
            return


        client_kwargs = {}
        if self.region:
            client_kwargs["region_name"] = self.region
        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url

        # profile works locally (shared credentials); on ECS you typically won't set it
        self._fs = s3fs.S3FileSystem(profile=self.profile, client_kwargs=client_kwargs)

    def _key(self, key: str) -> str:
        key = key.lstrip("/")
        pref = self.prefix.strip("/")
        return f"{pref}/{key}" if pref else key

    def _uri(self, key: str) -> str:
        return f"s3://{self.bucket}/{self._key(key)}"

    def exists(self, key: str) -> bool:
        self._init_fs()
        p = f"{self.bucket}/{self._key(key)}"   # NO s3://
        try:
            info = self._fs.info(p)             # raises if missing
            return info.get("type") == "file"
        except FileNotFoundError:
            return False
    

    def list(self, prefix: str) -> list[str]:
        self._init_fs()

        key_prefix = self._key(prefix).rstrip("/")
        root = f"{self.bucket}/{key_prefix}" if key_prefix else f"{self.bucket}/{self.prefix.strip('/')}".rstrip("/")
        # s3fs.find expects "bucket/prefix" (no s3://)
        try:
            paths = self._fs.find(root)
        except FileNotFoundError:
            return []

        out = []
        for p in paths:
            # p is like "bucket/prefix/...."
            if p.startswith(f"{self.bucket}/"):
                k = p[len(self.bucket) + 1 :]
            else:
                k = p

            pref = self.prefix.strip("/")
            if pref and k.startswith(pref + "/"):
                k = k[len(pref) + 1 :]

            out.append(k)

        return sorted(out)

    def delete_prefix(self, prefix: str) -> None:
        self._init_fs()
        normalized = prefix.strip("/")
        if not normalized:
            raise ValueError("Refusing to delete an empty storage prefix")

        target = f"{self.bucket}/{self._key(normalized)}"
        if self._fs.exists(target):
            self._fs.rm(target, recursive=True)
    
    def read_parquet(self, key: str) -> pd.DataFrame:
        self._init_fs()
        return pd.read_parquet(
                self._uri(key),
                engine="pyarrow",
                filesystem=self._fs,
                partitioning=None,   # <-- disables hive inference
            )

    def write_parquet(self, df: pd.DataFrame, key: str) -> None:
        self._init_fs()
        tmp_key = f"{self._key(key)}.__tmp__{uuid.uuid4().hex}"
        tmp_uri = f"s3://{self.bucket}/{tmp_key}"

        df.to_parquet(
            tmp_uri,
            index=False,
            engine="pyarrow",
            compression="zstd",
            filesystem=self._fs,
        )

        src = f"{self.bucket}/{tmp_key}"
        dst = f"{self.bucket}/{self._key(key)}"
        self._fs.copy(src, dst)

        try:
            self._fs.rm(src)
        except Exception:
            pass
    
    # =====================
    # CSV
    # =====================

    def read_csv(self, key: str) -> pd.DataFrame:
        self._init_fs()

        return pd.read_csv(
            self._uri(key),
            storage_options={
                "profile": self.profile,
            } if self.profile else None,
        )


    def write_csv(
        self,
        df: pd.DataFrame,
        key: str,
        index: bool = False,
    ) -> None:
        self._init_fs()

        tmp_key = (
            f"{self._key(key)}"
            f".__tmp__{uuid.uuid4().hex}"
        )

        tmp_uri = f"s3://{self.bucket}/{tmp_key}"

        df.to_csv(
            tmp_uri,
            index=index,
            storage_options={
                "profile": self.profile,
            } if self.profile else None,
        )

        src = f"{self.bucket}/{tmp_key}"
        dst = f"{self.bucket}/{self._key(key)}"

        self._fs.copy(src, dst)

        try:
            self._fs.rm(src)
        except Exception:
            pass

    def read_json(self, key: str) -> Any:
        self._init_fs()
        uri = self._uri(key)
        with self._fs.open(uri, "r") as f:
            return json.load(f)

    def write_json(self, obj: Any, key: str) -> None:
        self._init_fs()
        final_uri = self._uri(key)

        tmp_key = f"{self._key(key)}.__tmp__{uuid.uuid4().hex}"
        tmp_uri = f"s3://{self.bucket}/{tmp_key}"

        with self._fs.open(tmp_uri, "w") as f:
            json.dump(obj, f, indent=2, sort_keys=True, default=str)

        src = f"{self.bucket}/{tmp_key}"
        dst = f"{self.bucket}/{self._key(key)}"
        self._fs.copy(src, dst)

        try:
            self._fs.rm(src)
        except Exception:
            pass

    def read_pickle(self, key: str) -> Any:
        """
        Read a python object serialized via pickle from S3.
        """
        self._init_fs()
        uri = self._uri(key)
        with self._fs.open(uri, "rb") as f:
            return pickle.load(f)

    def write_pickle(self, obj: Any, key: str) -> None:
        """
        Write a python object to S3 using pickle, with best-effort atomic write:
        write temp -> copy to final -> delete temp.
        """
        self._init_fs()

        # temp key alongside final
        tmp_key = f"{self._key(key)}.__tmp__{uuid.uuid4().hex}"
        tmp_uri = f"s3://{self.bucket}/{tmp_key}"

        # write temp
        with self._fs.open(tmp_uri, "wb") as f:
            pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)

        # copy temp -> final (overwrite)
        src = f"{self.bucket}/{tmp_key}"
        dst = f"{self.bucket}/{self._key(key)}"
        self._fs.copy(src, dst)

        # cleanup temp
        try:
            self._fs.rm(src)
        except Exception:
            pass