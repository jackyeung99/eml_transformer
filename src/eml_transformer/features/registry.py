from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pandas as pd

from eml_transformer.features.builder import (
    build_eia_interchange_features,
    build_eia_region_features,
    build_hourly_text_features,
)


FeatureFunction = Callable[[pd.DataFrame], pd.DataFrame]


FEATURE_BUILDERS: dict[str, FeatureFunction] = {
    "eia_region": build_eia_region_features,
    "eia_interchange": build_eia_interchange_features,
    "text_hourly": build_hourly_text_features,
}


FEATURE_INPUTS: dict[str, dict[str, Any]] = {
    "eia_region": {
        "layer": "silver",
        "names": ("eia930_region",),
    },
    "eia_interchange": {
        "layer": "silver",
        "names": ("eia930_interchange",),
    },
    "text_hourly": {
        "layer": "embeddings",
        "names": (
            "gdelt",
            "iem_afos",
            "miso_notifications",
        ),
    },
}


def get_feature_function(name: str) -> FeatureFunction:
    try:
        return FEATURE_BUILDERS[name]
    except KeyError as error:
        available = ", ".join(sorted(FEATURE_BUILDERS))
        raise ValueError(
            f"Unknown feature set: {name!r}. Available: {available}"
        ) from error


def get_feature_inputs(name: str) -> dict[str, Any]:
    try:
        return FEATURE_INPUTS[name]
    except KeyError as error:
        available = ", ".join(sorted(FEATURE_INPUTS))
        raise ValueError(
            f"No inputs configured for feature set {name!r}. "
            f"Available: {available}"
        ) from error