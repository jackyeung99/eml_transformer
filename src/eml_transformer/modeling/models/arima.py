from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.arima.model import ARIMAResults


from eml_transformer.modeling.models.base import BaseForecastModel, FloatArray
from eml_transformer.modeling.models.statsmodels import (
    extract_statsmodels_diagnostics,
)

class ArimaForecastModel(BaseForecastModel):
    def __init__(
        self,
        *,
        order: tuple[int, int, int] = (1, 0, 0),
        trend: str | None = None,
        use_exogenous: bool = False,
        enforce_stationarity: bool = True,
        enforce_invertibility: bool = True,
    ) -> None:
        self.order = order
        self.trend = trend
        self.use_exogenous = use_exogenous
        self.enforce_stationarity = enforce_stationarity
        self.enforce_invertibility = enforce_invertibility

    @property
    def requires_exogenous(self) -> bool:
        return self.use_exogenous

    def _fit_model(
        self,
        X: FloatArray | None,
        y: FloatArray,
    ) -> None:
        self.estimator_ = ARIMA(
            endog=y,
            exog=X,
            order=self.order,
            trend=self.trend,
            enforce_stationarity=self.enforce_stationarity,
            enforce_invertibility=self.enforce_invertibility,
        )

        self.results_ = self.estimator_.fit()

    def _forecast_model(
        self,
        *,
        steps: int,
        X: FloatArray | None,
    ) -> FloatArray:
        predictions = self.results_.forecast(
            steps=steps,
            exog=X,
        )

        return np.asarray(predictions, dtype=float)

    def _build_diagnostics(
        self,
        X: FloatArray | None,
        y: FloatArray,
    ) -> dict[str, Any]:
        diagnostics = extract_statsmodels_diagnostics(
            self.results_
        )
        diagnostics.update(
            {
                "order": list(self.order),
                "trend": self.trend,
                "uses_exogenous_features": (
                    self.use_exogenous
                ),
            }
        )
        return diagnostics