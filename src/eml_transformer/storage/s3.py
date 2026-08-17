from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any
import json
import pickle
import uuid

import pandas as pd
import s3fs

from eml_transformer.storage.base import Storage
from eml_transformer.storage.paths import StoragePaths


@dataclass
class S3Storage(Storage):
    """
    S3-backed storage using s3fs.

    Storage keys are relative to the configured bucket and prefix.

    Example:
        bucket="my-bucket"
        prefix="eml-transformer"
        key="data/bronze/source=eia_region/records.jsonl"

    Result:
        s3://my-bucket/eml-transformer/data/bronze/
        source=eia_region/records.jsonl

    Writes use a best-effort replacement strategy:

        temporary object -> copy to final object -> delete temporary object

    S3 does not provide true atomic rename or in-place append.
    """

    paths: StoragePaths
    bucket: str
    prefix: str = ""

    region: str | None = None
    profile: str | None = None
    endpoint_url: str | None = None

    _fs: Any = field(
        init=False,
        repr=False,
        default=None,
    )

    def _init_fs(self) -> None:
        if self._fs is not None:
            return

        client_kwargs: dict[str, Any] = {}

        if self.region:
            client_kwargs["region_name"] = self.region

        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url

        options: dict[str, Any] = {
            "client_kwargs": client_kwargs,
        }

        if self.profile:
            options["profile"] = self.profile

        self._fs = s3fs.S3FileSystem(**options)

    def _key(self, key: str) -> str:
        """
        Add the configured storage prefix to a relative storage key.
        """
        normalized_key = key.strip("/")
        normalized_prefix = self.prefix.strip("/")

        if not normalized_prefix:
            return normalized_key

        if not normalized_key:
            return normalized_prefix

        return f"{normalized_prefix}/{normalized_key}"

    def _s3_path(self, key: str) -> str:
        """
        Return an s3fs-compatible path without the s3:// scheme.
        """
        storage_key = self._key(key)

        if storage_key:
            return f"{self.bucket}/{storage_key}"

        return self.bucket

    def _uri(self, key: str) -> str:
        """
        Return a complete S3 URI for display or external consumers.
        """
        return f"s3://{self._s3_path(key)}"

    def _temporary_path(self, key: str) -> str:
        """
        Return a temporary S3 path next to the final object.
        """
        return (
            f"{self._s3_path(key)}"
            f".__tmp__{uuid.uuid4().hex}"
        )

    def _promote_temporary_object(
        self,
        *,
        temporary_path: str,
        final_path: str,
    ) -> None:
        """
        Copy a temporary object to its final location.

        S3 copy is not a truly atomic rename.
        """
        self._fs.copy(
            temporary_path,
            final_path,
        )

    def _delete_temporary_object(
        self,
        temporary_path: str,
    ) -> None:
        """
        Best-effort cleanup of a temporary object.
        """
        try:
            if self._fs.exists(temporary_path):
                self._fs.rm(temporary_path)
        except Exception:
            # Do not mask the original write or copy exception.
            pass

    # =====================
    # General operations
    # =====================

    def exists(self, key: str) -> bool:
        self._init_fs()
        return self._fs.exists(self._s3_path(key))

    def list(self, prefix: str) -> list[str]:
        self._init_fs()

        target = self._s3_path(prefix)

        if not self._fs.exists(target):
            return []

        try:
            information = self._fs.info(target)

            if information.get("type") == "file":
                return [prefix.strip("/")]

            paths = self._fs.find(target)

        except FileNotFoundError:
            return []

        storage_prefix = self.prefix.strip("/")
        bucket_prefix = f"{self.bucket}/"

        output: list[str] = []

        for path in paths:
            key = path

            if key.startswith(bucket_prefix):
                key = key[len(bucket_prefix):]

            if storage_prefix:
                prefix_with_separator = (
                    f"{storage_prefix}/"
                )

                if key.startswith(prefix_with_separator):
                    key = key[
                        len(prefix_with_separator):
                    ]
                elif key == storage_prefix:
                    key = ""

            if key:
                output.append(key)

        return sorted(output)

    def delete_prefix(self, prefix: str) -> None:
        self._init_fs()

        normalized_prefix = prefix.strip("/")

        if not normalized_prefix:
            raise ValueError(
                "Refusing to delete an empty storage prefix"
            )

        target = self._s3_path(normalized_prefix)

        if target == self.bucket:
            raise ValueError(
                "Refusing to delete the storage bucket"
            )

        if self._fs.exists(target):
            self._fs.rm(
                target,
                recursive=True,
            )

    # =====================
    # Parquet
    # =====================

    def read_parquet(
        self,
        key: str,
    ) -> pd.DataFrame:
        self._init_fs()

        path = self._s3_path(key)

        with self._fs.open(path, "rb") as file:
            return pd.read_parquet(
                file,
                engine="pyarrow",
                dtype_backend="pyarrow",
            )

    def write_parquet(
        self,
        df: pd.DataFrame,
        key: str,
    ) -> None:
        self._init_fs()

        final_path = self._s3_path(key)
        temporary_path = self._temporary_path(key)

        try:
            with self._fs.open(
                temporary_path,
                "wb",
            ) as file:
                df.to_parquet(
                    file,
                    engine="pyarrow",
                    compression="zstd",
                    index=False,
                )

            self._promote_temporary_object(
                temporary_path=temporary_path,
                final_path=final_path,
            )

        finally:
            self._delete_temporary_object(
                temporary_path
            )

    # =====================
    # CSV
    # =====================

    def read_csv(
        self,
        key: str,
    ) -> pd.DataFrame:
        self._init_fs()

        path = self._s3_path(key)

        with self._fs.open(path, "rb") as file:
            return pd.read_csv(file)

    def write_csv(
        self,
        df: pd.DataFrame,
        key: str,
        index: bool = False,
    ) -> None:
        self._init_fs()

        final_path = self._s3_path(key)
        temporary_path = self._temporary_path(key)

        try:
            with self._fs.open(
                temporary_path,
                "w",
                encoding="utf-8",
            ) as file:
                df.to_csv(
                    file,
                    index=index,
                )

            self._promote_temporary_object(
                temporary_path=temporary_path,
                final_path=final_path,
            )

        finally:
            self._delete_temporary_object(
                temporary_path
            )

    # =====================
    # JSON
    # =====================

    def read_json(
        self,
        key: str,
    ) -> Any:
        self._init_fs()

        path = self._s3_path(key)

        with self._fs.open(
            path,
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    def write_json(
        self,
        obj: Any,
        key: str,
    ) -> None:
        self._init_fs()

        final_path = self._s3_path(key)
        temporary_path = self._temporary_path(key)

        try:
            with self._fs.open(
                temporary_path,
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    obj,
                    file,
                    indent=2,
                    sort_keys=True,
                    default=str,
                )

            self._promote_temporary_object(
                temporary_path=temporary_path,
                final_path=final_path,
            )

        finally:
            self._delete_temporary_object(
                temporary_path
            )

    # =====================
    # JSONL
    # =====================

    def append_jsonl(
        self,
        key: str,
        rows: list[dict[str, Any]],
    ) -> None:
        """
        Append rows to a JSONL object.

        S3 does not support in-place append. This method streams the
        existing object into a temporary object, writes the new rows,
        and replaces the final object.

        Concurrent writers can overwrite each other's changes. Use
        partitioned Bronze objects before enabling concurrent ingestion.
        """
        if not rows:
            return

        self._init_fs()

        final_path = self._s3_path(key)
        temporary_path = self._temporary_path(key)

        try:
            with self._fs.open(
                temporary_path,
                "wb",
            ) as destination:
                last_byte: bytes | None = None

                if self._fs.exists(final_path):
                    with self._fs.open(
                        final_path,
                        "rb",
                    ) as source:
                        while True:
                            chunk = source.read(
                                1024 * 1024
                            )

                            if not chunk:
                                break

                            destination.write(chunk)
                            last_byte = chunk[-1:]

                if (
                    last_byte is not None
                    and last_byte != b"\n"
                ):
                    destination.write(b"\n")

                for row in rows:
                    encoded = json.dumps(
                        row,
                        ensure_ascii=False,
                    ).encode("utf-8")

                    destination.write(encoded)
                    destination.write(b"\n")

            self._promote_temporary_object(
                temporary_path=temporary_path,
                final_path=final_path,
            )

        finally:
            self._delete_temporary_object(
                temporary_path
            )

    def iter_jsonl(
        self,
        key: str,
    ) -> Iterator[dict[str, Any]]:
        self._init_fs()

        path = self._s3_path(key)

        try:
            with self._fs.open(path, "rb") as file:
                for line_number, line in enumerate(
                    file,
                    start=1,
                ):
                    line = line.strip()

                    if not line:
                        continue

                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError as error:
                        raise ValueError(
                            f"Invalid JSONL in {key!r} "
                            f"at line {line_number}"
                        ) from error

                    if not isinstance(row, dict):
                        raise ValueError(
                            f"Expected a JSON object in "
                            f"{key!r} at line "
                            f"{line_number}, received "
                            f"{type(row).__name__}"
                        )

                    yield row

        except FileNotFoundError:
            return

    def read_jsonl(
        self,
        key: str,
    ) -> list[dict[str, Any]]:
        return list(self.iter_jsonl(key))

    # =====================
    # Pickle
    # =====================

    def read_pickle(
        self,
        key: str,
    ) -> Any:
        self._init_fs()

        path = self._s3_path(key)

        with self._fs.open(path, "rb") as file:
            return pickle.load(file)

    def write_pickle(
        self,
        obj: Any,
        key: str,
    ) -> None:
        self._init_fs()

        final_path = self._s3_path(key)
        temporary_path = self._temporary_path(key)

        try:
            with self._fs.open(
                temporary_path,
                "wb",
            ) as file:
                pickle.dump(
                    obj,
                    file,
                    protocol=pickle.HIGHEST_PROTOCOL,
                )

            self._promote_temporary_object(
                temporary_path=temporary_path,
                final_path=final_path,
            )

        finally:
            self._delete_temporary_object(
                temporary_path
            )