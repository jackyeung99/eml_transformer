import pandas as pd




def build_load_forecast_dataset(
    inputs: list[pd.DataFrame],
    *,
    target: str = "actual_load",
) -> pd.DataFrame:
    region_features = inputs[0]


    interchange_features = inputs[1]

    return region_features.merge(
        interchange_features,
        on=["observed_at", "region"],
        how="left",
    )