from collections.abc import Callable
from typing import Any

from sklearn.base import BaseEstimator
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge


ModelFactory = Callable[..., BaseEstimator]


MODEL_FACTORIES: dict[str, ModelFactory] = {
    "ridge": Ridge,
    "random_forest": RandomForestRegressor,
    # "custom_load": CustomLoadModel,
}


def create_model(
    name: str,
    settings: dict[str, Any] | None = None,
) -> BaseEstimator:
    try:
        factory = MODEL_FACTORIES[name]
    except KeyError:
        available = ", ".join(sorted(MODEL_FACTORIES))
        raise ValueError(
            f"Unknown model {name!r}. Available models: {available}"
        ) from None

    return factory(**(settings or {}))