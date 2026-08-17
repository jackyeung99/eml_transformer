from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pandas as pd

from eml_transformer.features.builder import (
    build_eia_region_hourly,
    build_eia_region_daily,
    build_eia_interchange_features, 
    build_eia_interchange_daily

)


FeatureFunction = Callable[[pd.DataFrame], pd.DataFrame]


FEATURE_BUILDERS: dict[str, FeatureFunction] = {
    "eia_region_hourly": build_eia_region_hourly,
    "eia_region_daily": build_eia_region_daily,
    "eia_interchange_hourly": build_eia_interchange_features,
    "eia_interchange_daily": build_eia_interchange_daily
}



def get_feature_function(name: str) -> FeatureFunction:
    try:
        return FEATURE_BUILDERS[name]
    except KeyError as error:
        available = ", ".join(sorted(FEATURE_BUILDERS))
        raise ValueError(
            f"Unknown feature set: {name!r}. Available: {available}"
        ) from error


