from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from eml_transformer.features.transformations.reshape import (
    long_to_wide,
)



def build_eia_region_features(
    records: pd.DataFrame,
) -> pd.DataFrame:
    columns = [
        "observed_at",
        "region",
        "variable",
        "value",
    ]

    return long_to_wide(
        records.loc[:, columns],
        index_columns=["observed_at", "region"],
    )


def build_eia_interchange_features(
    records: pd.DataFrame,
) -> pd.DataFrame:
    frame = records.copy()

    # Remove these lines if dimensions were already expanded in Silver.
    if "from_region" not in frame.columns:
        frame["from_region"] = frame["dimensions"].map(
            lambda value: value.get("from_region")
        )

    if "to_region" not in frame.columns:
        frame["to_region"] = frame["dimensions"].map(
            lambda value: value.get("to_region")
        )

    imports = (
        frame.groupby(
            ["observed_at", "to_region"],
            as_index=False,
        )["value"]
        .sum()
        .rename(
            columns={
                "to_region": "region",
                "value": "total_imports",
            }
        )
    )

    exports = (
        frame.groupby(
            ["observed_at", "from_region"],
            as_index=False,
        )["value"]
        .sum()
        .rename(
            columns={
                "from_region": "region",
                "value": "total_exports",
            }
        )
    )

    result = imports.merge(
        exports,
        on=["observed_at", "region"],
        how="outer",
        validate="one_to_one",
    )

    result[["total_imports", "total_exports"]] = result[
        ["total_imports", "total_exports"]
    ].fillna(0.0)

    result["net_imports"] = (
        result["total_imports"] - result["total_exports"]
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

