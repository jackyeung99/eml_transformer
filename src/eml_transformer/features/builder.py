from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from eml_transformer.features.transformations.reshape import (
    long_to_wide, expand_dimensions
)

from eml_transformer.features.transformations.calendar import (
    add_calendar_features, add_holiday_feature, add_local_timestamp
)

from eml_transformer.features.transformations.temporal import (
    add_lags
)


def build_eia_region_hourly(
    df: pd.DataFrame,
) -> pd.DataFrame:
    features = expand_dimensions(df)

    columns = [
        "observed_at",
        "region",
        "variable",
        "value",
    ]

    features = long_to_wide(
        features.loc[:, columns],
        index_columns=["observed_at", "region"],
    )

    features = add_local_timestamp(
        features,
        source_column="observed_at",
        output_column="observed_at_eta",
        timezone="America/New_York",
    )

    features = add_lags(
        features,
        column="actual_load",
        lags=(1, 24, 168),
        group_by="region",
        time_column="observed_at",
    )

    features = add_calendar_features(
        features,
        time_column="observed_at_eta",
    )

    features = add_holiday_feature(
        features,
        time_column="observed_at_eta",
        timezone="America/New_York",
    )

    return features


def build_eia_region_daily(df: pd.DataFrame) -> pd.DataFrame:
    wide = build_eia_region_hourly(df)

    return (
        wide
        .set_index("observed_at")
        .resample("1D")
        .agg(
            load_mean=("actual_load", "mean"),
            load_min=("actual_load", "min"),
            load_max=("actual_load", "max"),
            generation_total=("net_generation", "sum"),
        )
        .reset_index()
    )


MISO_REGION = "Midcontinent Independent System Operator, Inc."


def build_eia_interchange_features(
    df: pd.DataFrame,
) -> pd.DataFrame:
    expanded = expand_dimensions(df)
    index_columns = ["observed_at", "region"]

    imports = (
        expanded.loc[
            expanded["to_region"].eq(MISO_REGION),
            index_columns + ["value"],
        ]
        .groupby(index_columns, as_index=False)["value"]
        .sum()
        .rename(columns={"value": "total_imports"})
    )

    exports = (
        expanded.loc[
            expanded["from_region"].eq(MISO_REGION),
            index_columns + ["value"],
        ]
        .groupby(index_columns, as_index=False)["value"]
        .sum()
        .rename(columns={"value": "total_exports"})
    )

    features = (
        imports.merge(
            exports,
            on=index_columns,
            how="outer",
        )
        .sort_values(["region", "observed_at"])
        .reset_index(drop=True)
    )

    features["total_imports_lag_24"] = (
        features.groupby("region")["total_imports"].shift(24)
    )

    features["total_exports_lag_24"] = (
        features.groupby("region")["total_exports"].shift(24)
    )

    return features[
        [
            "observed_at",
            "region",
            "total_imports_lag_24",
            "total_exports_lag_24",
        ]
    ]

# def build_iem_afos_features(df: pd.DataFrame) -> pd.DataFrame:
#     scored = add_iem_severity(df)

#     return aggregate_hourly_severity(
#         scored,
#         group_columns=("source", "region"),
#     )


# def build_gdelt_features(df: pd.DataFrame) -> pd.DataFrame:
#     scored = add_gdelt_severity(df)

#     return aggregate_hourly_severity(
#         scored,
#         group_columns=("source", "region"),
#     )
