from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.statespace.sarimax import SARIMAXResults

from eml_transformer.modeling.models.base import BaseForecastModel
from eml_transformer.modeling.models.statsmodels import (
    extract_statsmodels_diagnostics,
)

class SarimaxForecastModel(BaseForecastModel):
    def __init__(
        self,
        *,
        order: tuple[int, int, int] = (1, 0, 0),
        seasonal_order: tuple[int, int, int, int] = (
            0,
            0,
            0,
            0,
        ),
        trend: str | None = None,
        use_exogenous: bool = True,
        enforce_stationarity: bool = True,
        enforce_invertibility: bool = True,
        simple_differencing: bool = False,
    ) -> None:
        self.order = order
        self.seasonal_order = seasonal_order
        self.trend = trend
        self.use_exogenous = use_exogenous
        self.enforce_stationarity = enforce_stationarity
        self.enforce_invertibility = enforce_invertibility
        self.simple_differencing = simple_differencing

    def _fit_model(
        self,
        X: NDArray[np.float64],
        y: NDArray[np.float64],
    ) -> None:
        exogenous = X if self.use_exogenous else None

        self.estimator_ = SARIMAX(
            endog=y,
            exog=exogenous,
            order=self.order,
            seasonal_order=self.seasonal_order,
            trend=self.trend,
            enforce_stationarity=self.enforce_stationarity,
            enforce_invertibility=self.enforce_invertibility,
            simple_differencing=self.simple_differencing,
        )

        self.results_ = self.estimator_.fit(
            disp=False,
        )

    def _predict_model(
        self,
        X: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        exogenous = X if self.use_exogenous else None

        forecast = self.results_.forecast(
            steps=len(X),
            exog=exogenous,
        )

        return np.asarray(forecast, dtype=float)

    def _build_diagnostics(
        self,
        X: NDArray[np.float64],
        y: NDArray[np.float64],
    ) -> dict[str, Any]:
        diagnostics = extract_statsmodels_diagnostics(
            self.results_
        )

        diagnostics.update(
            {
                "order": list(self.order),
                "seasonal_order": list(
                    self.seasonal_order
                ),
                "trend": self.trend,
                "uses_exogenous_features": (
                    self.use_exogenous
                ),
                "simple_differencing": (
                    self.simple_differencing
                ),
            }
        )

        return diagnostics