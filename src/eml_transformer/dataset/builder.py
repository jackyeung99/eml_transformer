import pandas as pd
from collections.abc import Mapping



def build_load_forecast_dataset(
    inputs: Mapping[str, pd.DataFrame],
    *,
    target: str = "actual_load",
) -> pd.DataFrame:
    region_features = inputs["region_features"]
    interchange_features = inputs["interchange_features"]

    if target not in region_features.columns:
        raise ValueError(
            f"Target {target!r} is missing from region_features"
        )

    return region_features.merge(
        interchange_features,
        on=["observed_at", "region"],
        how="left",
        validate="one_to_one",
    )

def build_daily_load_forecast_dataset(
    inputs: Mapping[str, pd.DataFrame],
    *,
    target: str = "load_max",
) -> pd.DataFrame:
    region_features = inputs["region_daily_features"]
    interchange_features = inputs["interchange_daily_features"]

    if target not in region_features.columns:
        raise ValueError(
            f"Target {target!r} is missing from "
            "region_daily_features"
        )

    return (
        region_features.merge(
            interchange_features,
            on=["observed_at", "region"],
            how="left",
            validate="one_to_one",
        )
        .sort_values(["region", "observed_at"])
        .reset_index(drop=True)
    )