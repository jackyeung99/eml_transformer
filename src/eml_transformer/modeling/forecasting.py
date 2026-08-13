
from __future__ import annotations

import pandas as pd
from sklearn.base import RegressorMixin


def generate_forecast(
    model: RegressorMixin,
    data: pd.DataFrame,
    *,
    features: tuple[str, ...],
) -> pd.DataFrame:
    missing = set(features).difference(data.columns)

    if missing:
        raise ValueError(
            f"Missing forecast features: {sorted(missing)}"
        )

    forecasts = data.loc[:, ["observed_at", "region"]].copy()
    forecasts["forecast"] = model.predict(
        data.loc[:, features]
    )

    return forecasts