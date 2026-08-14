from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from eml_transformer.modeling.models.arima import (
    ArimaForecastModel,
)
from eml_transformer.modeling.models.base import (
    BaseForecastModel,
)
from eml_transformer.modeling.models.ridge import (
    RidgeForecastModel,
)
from eml_transformer.modeling.models.sarimax import (
    SarimaxForecastModel,
)


ModelFactory = Callable[..., BaseForecastModel]


MODEL_FACTORIES: dict[str, ModelFactory] = {
    "arima": ArimaForecastModel,
    "ridge": RidgeForecastModel,
    "sarimax": SarimaxForecastModel,
}


def create_model(
    name: str,
    settings: Mapping[str, Any] | None = None,
) -> BaseForecastModel:
    try:
        factory = MODEL_FACTORIES[name]
    except KeyError:
        available = ", ".join(
            sorted(MODEL_FACTORIES)
        )

        raise ValueError(
            f"Unknown model {name!r}. "
            f"Available models: {available}"
        ) from None

    return factory(**dict(settings or {}))