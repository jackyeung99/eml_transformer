from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pandas as pd

from eml_transformer.dataset.builder import (
    build_load_forecast_dataset,
    build_daily_load_forecast_dataset
)

DatasetFunction = Callable[..., pd.DataFrame]


DATASET_BUILDERS: dict[str, DatasetFunction] = {
    "hourly_load_forecasting": build_load_forecast_dataset,
    "daily_load_forecasting": build_daily_load_forecast_dataset
}


def get_dataset_function(name: str) -> DatasetFunction:
    try:
        return DATASET_BUILDERS[name]
    except KeyError as error:
        available = ", ".join(sorted(DATASET_BUILDERS))

        raise ValueError(
            f"Unknown dataset: {name!r}. Available: {available}"
        ) from error