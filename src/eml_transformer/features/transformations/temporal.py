from __future__ import annotations

from collections.abc import Iterable

import pandas as pd
import numpy as np


def add_lags(
    df: pd.DataFrame,
    *,
    column: str,
    lags: tuple[int, ...],
    group_by: str | list[str] | None = None,
    time_column: str = "observed_at",
) -> pd.DataFrame:
    """
    Add row-based lag features.

    Assumes each group contains one row per hour.
    """
    if column not in df.columns:
        raise KeyError(f"Missing lag column: {column!r}")

    result = df.copy()

    sort_columns = (
        [group_by, time_column]
        if isinstance(group_by, str)
        else [*(group_by or []), time_column]
    )
    result = result.sort_values(sort_columns)

    for lag in lags:
        if lag <= 0:
            raise ValueError("Lags must be greater than zero")

        if group_by:
            result[f"{column}_lag_{lag}"] = (
                result.groupby(group_by, sort=False)[column]
                .shift(lag)
            )
        else:
            result[f"{column}_lag_{lag}"] = result[column].shift(lag)

    return result


def add_rolling_means(
    frame: pd.DataFrame,
    columns: Iterable[str],
    windows: Iterable[int],
    group_by: str | None = "region",
) -> pd.DataFrame:
    result = frame.copy()

    for column in columns:
        for window in windows:
            name = f"{column}_rolling_mean_{window}"

            if group_by:
                result[name] = (
                    result.groupby(group_by, sort=False)[column]
                    .transform(
                        lambda values: values
                        .shift(1)
                        .rolling(window)
                        .mean()
                    )
                )
            else:
                result[name] = (
                    result[column]
                    .shift(1)
                    .rolling(window)
                    .mean()
                )

    return result


def _mean_embeddings(
    values: pd.Series,
) -> list[float]:
    arrays = [
        np.asarray(value, dtype=np.float32)
        for value in values
        if value is not None
    ]

    if not arrays:
        return []

    return np.stack(arrays).mean(axis=0).tolist()


def build_hourly_text_features(
    records: pd.DataFrame,
) -> pd.DataFrame:
    frame = records.copy()

    frame["published_at"] = pd.to_datetime(
        frame["published_at"],
        utc=True,
    )

    frame["observed_at"] = frame["published_at"].dt.floor("h")

    return (
        frame.groupby(
            ["observed_at", "region"],
            as_index=False,
            dropna=False,
        )
        .agg(
            article_count=("record_id", "count"),
            embedding=("embedding", _mean_embeddings),
        )
    )

