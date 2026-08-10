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


def build_eia_region_features(
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


def build_eia_interchange_features(
    df: pd.DataFrame,
) -> pd.DataFrame:

    features = expand_dimensions(df)
    return features



def build_iem_afos_features(df: pd.DataFrame) -> pd.DataFrame:
    scored = add_iem_severity(df)

    return aggregate_hourly_severity(
        scored,
        group_columns=("source", "region"),
    )


def build_gdelt_features(df: pd.DataFrame) -> pd.DataFrame:
    scored = add_gdelt_severity(df)

    return aggregate_hourly_severity(
        scored,
        group_columns=("source", "region"),
    )
