from __future__ import annotations

from collections.abc import Iterable, Iterator
from copy import deepcopy
from typing import Any

import pandas as pd

from eml_transformer.storage.base import Storage
from eml_transformer.storage.paths import StoragePaths




class FakeStorage(Storage):
    """
    In-memory storage for stage and pipeline tests.

    Logical datasets are stored as one DataFrame. The fake preserves
    the public batching interface without reproducing physical
    Parquet part files.
    """

    def __init__(
        self,
        paths: StoragePaths,
    ) -> None:
        self.paths = paths

        self.parquet_data: dict[
            str,
            pd.DataFrame,
        ] = {}
        self.csv_data: dict[
            str,
            pd.DataFrame,
        ] = {}
        self.json_data: dict[
            str,
            Any,
        ] = {}
        self.jsonl_data: dict[
            str,
            list[dict[str, Any]],
        ] = {}
        self.pickle_data: dict[
            str,
            Any,
        ] = {}

        # Interaction tracking.
        self.parquet_write_calls: list[
            tuple[str, pd.DataFrame]
        ] = []
        self.csv_write_calls: list[
            tuple[str, pd.DataFrame, bool]
        ] = []
        self.json_write_calls: list[
            tuple[str, Any]
        ] = []
        self.jsonl_append_calls: list[
            tuple[str, list[dict[str, Any]]]
        ] = []
        self.pickle_write_calls: list[
            tuple[str, Any]
        ] = []
        self.batch_write_calls: list[
            tuple[str, list[pd.DataFrame], str]
        ] = []

        # Optional failure injection.
        self.write_errors: dict[
            str,
            Exception,
        ] = {}
        self.append_errors: dict[
            str,
            Exception,
        ] = {}
        self.read_errors: dict[
            str,
            Exception,
        ] = {}

    # =====================
    # General objects
    # =====================

    def exists(
        self,
        key: str,
    ) -> bool:
        if key in self._all_keys():
            return True

        normalized_prefix = key.rstrip("/") + "/"

        return any(
            stored_key.startswith(normalized_prefix)
            for stored_key in self._all_keys()
        )

    def list(
        self,
        prefix: str,
    ) -> list[str]:
        normalized_prefix = prefix.rstrip("/") + "/"

        return sorted(
            key
            for key in self._all_keys()
            if (
                key == prefix
                or key.startswith(normalized_prefix)
            )
        )

    def delete_prefix(
        self,
        prefix: str,
    ) -> None:
        normalized_prefix = prefix.rstrip("/") + "/"

        for store in self._stores():
            matching_keys = [
                key
                for key in store
                if (
                    key == prefix
                    or key.startswith(normalized_prefix)
                )
            ]

            for key in matching_keys:
                del store[key]

    # =====================
    # Parquet
    # =====================

    def read_parquet(
        self,
        key: str,
    ) -> pd.DataFrame:
        self._raise_read_error(key)

        if key not in self.parquet_data:
            raise FileNotFoundError(key)

        return self.parquet_data[
            key
        ].copy(deep=True)

    def write_parquet(
        self,
        df: pd.DataFrame,
        key: str,
    ) -> None:
        self._raise_write_error(key)

        copied_df = df.copy(deep=True)
        self.parquet_data[key] = copied_df

        self.parquet_write_calls.append(
            (
                key,
                copied_df.copy(deep=True),
            )
        )

    # =====================
    # Collapsed datasets
    # =====================

    def read_batches(
        self,
        ref: DatasetRef | str,
    ) -> Iterator[pd.DataFrame]:
        """
        Yield the complete logical dataset as one batch.
        """
        key = self.paths.dataset(ref)
        self._raise_read_error(key)

        if key in self.parquet_data:
            yield self.parquet_data[
                key
            ].copy(deep=True)

    def write_batches(
        self,
        ref: DatasetRef | str,
        batches: Iterable[pd.DataFrame],
        *,
        mode: str = "replace",
    ) -> int:
        """
        Collapse incoming batches into one in-memory DataFrame.
        """
        if mode not in {"replace", "append"}:
            raise ValueError(
                f"Unsupported write mode: {mode!r}"
            )

        key = self.paths.dataset(ref)
        self._raise_write_error(key)

        copied_batches = [
            frame.copy(deep=True)
            for frame in batches
            if not frame.empty
        ]

        self.batch_write_calls.append(
            (
                key,
                [
                    frame.copy(deep=True)
                    for frame in copied_batches
                ],
                mode,
            )
        )

        records_written = sum(
            len(frame)
            for frame in copied_batches
        )

        if mode == "replace":
            self.delete_prefix(key)

        if not copied_batches:
            return 0

        incoming = pd.concat(
            copied_batches,
            ignore_index=True,
        )

        if (
            mode == "append"
            and key in self.parquet_data
        ):
            combined = pd.concat(
                [
                    self.parquet_data[key],
                    incoming,
                ],
                ignore_index=True,
            )
        else:
            combined = incoming

        self.write_parquet(
            combined,
            key,
        )

        return records_written

    # `read_dataset`, `write_records`, `write_dataframe`, and
    # `write_forecasts` are inherited from Storage. They use the
    # collapsed read_batches/write_batches implementations above.

    # =====================
    # CSV
    # =====================

    def read_csv(
        self,
        key: str,
    ) -> pd.DataFrame:
        self._raise_read_error(key)

        if key not in self.csv_data:
            raise FileNotFoundError(key)

        return self.csv_data[
            key
        ].copy(deep=True)

    def write_csv(
        self,
        df: pd.DataFrame,
        key: str,
        index: bool = False,
    ) -> None:
        self._raise_write_error(key)

        copied_df = df.copy(deep=True)
        self.csv_data[key] = copied_df

        self.csv_write_calls.append(
            (
                key,
                copied_df.copy(deep=True),
                index,
            )
        )

    # =====================
    # JSON
    # =====================

    def read_json(
        self,
        key: str,
    ) -> Any:
        self._raise_read_error(key)

        if key not in self.json_data:
            raise FileNotFoundError(key)

        return deepcopy(
            self.json_data[key]
        )

    def write_json(
        self,
        obj: Any,
        key: str,
    ) -> None:
        self._raise_write_error(key)

        copied_obj = deepcopy(obj)
        self.json_data[key] = copied_obj

        self.json_write_calls.append(
            (
                key,
                deepcopy(copied_obj),
            )
        )

    # =====================
    # JSONL
    # =====================

    def iter_jsonl(
        self,
        key: str,
    ) -> Iterator[dict[str, Any]]:
        self._raise_read_error(key)

        if key not in self.jsonl_data:
            raise FileNotFoundError(key)

        for record in self.jsonl_data[key]:
            yield deepcopy(record)

    def append_jsonl(
        self,
        key: str,
        records: Iterable[dict[str, Any]],
    ) -> None:
        if key in self.append_errors:
            raise self.append_errors[key]

        copied_records = [
            deepcopy(record)
            for record in records
        ]

        self.jsonl_data.setdefault(
            key,
            [],
        ).extend(copied_records)

        self.jsonl_append_calls.append(
            (
                key,
                deepcopy(copied_records),
            )
        )

    # Optional convenience method for older tests.
    def read_jsonl(
        self,
        key: str,
    ) -> list[dict[str, Any]]:
        return list(self.iter_jsonl(key))

    # Optional convenience method for older tests.
    def write_jsonl(
        self,
        records: Iterable[dict[str, Any]],
        key: str,
    ) -> None:
        self._raise_write_error(key)

        copied_records = [
            deepcopy(record)
            for record in records
        ]

        self.jsonl_data[key] = copied_records

    # =====================
    # Pickle
    # =====================

    def read_pickle(
        self,
        key: str,
    ) -> Any:
        self._raise_read_error(key)

        if key not in self.pickle_data:
            raise FileNotFoundError(key)

        return deepcopy(
            self.pickle_data[key]
        )

    def write_pickle(
        self,
        obj: Any,
        key: str,
    ) -> None:
        self._raise_write_error(key)

        copied_obj = deepcopy(obj)
        self.pickle_data[key] = copied_obj

        self.pickle_write_calls.append(
            (
                key,
                deepcopy(copied_obj),
            )
        )

    # =====================
    # Helpers
    # =====================

    def _stores(
        self,
    ) -> tuple[dict[str, Any], ...]:
        return (
            self.parquet_data,
            self.csv_data,
            self.json_data,
            self.jsonl_data,
            self.pickle_data,
        )

    def _all_keys(
        self,
    ) -> set[str]:
        keys: set[str] = set()

        for store in self._stores():
            keys.update(store)

        return keys

    def _raise_write_error(
        self,
        key: str,
    ) -> None:
        if key in self.write_errors:
            raise self.write_errors[key]

    def _raise_read_error(
        self,
        key: str,
    ) -> None:
        if key in self.read_errors:
            raise self.read_errors[key]