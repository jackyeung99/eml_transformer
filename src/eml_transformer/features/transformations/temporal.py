from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


def add_lags(
    frame: pd.DataFrame,
    columns: Iterable[str],
    lags: Iterable[int],
    group_by: str | None = "region",
) -> pd.DataFrame:
    result = frame.copy()

    for column in columns:
        for lag in lags:
            name = f"{column}_lag_{lag}"

            if group_by:
                result[name] = (
                    result.groupby(group_by, sort=False)[column]
                    .shift(lag)
                )
            else:
                result[name] = result[column].shift(lag)

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