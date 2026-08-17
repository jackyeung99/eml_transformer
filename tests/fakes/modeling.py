from __future__ import annotations

from typing import Any

import pandas as pd


class FakeForecastModel:
    """
    Shared fake model for modeling unit tests.

    Supports both training and forecasting while recording all calls.
    """

    def __init__(
        self,
        *,
        requires_exogenous: bool = True,
        predictions: list[float] | None = None,
        diagnostics: dict[str, Any] | None = None,
        fit_error: Exception | None = None,
        forecast_error: Exception | None = None,
    ) -> None:
        self.requires_exogenous = requires_exogenous
        self.predictions = list(
            predictions or []
        )
        self.diagnostics_ = dict(
            diagnostics
            or {
                "fake_diagnostic": 123,
            }
        )

        self.fit_error = fit_error
        self.forecast_error = forecast_error

        self.fit_calls: list[
            dict[str, Any]
        ] = []
        self.forecast_calls: list[
            dict[str, Any]
        ] = []

    def fit(
        self,
        X: pd.DataFrame | None,
        y: pd.Series,
    ) -> FakeForecastModel:
        self.fit_calls.append(
            {
                "X": (
                    X.copy(deep=True)
                    if X is not None
                    else None
                ),
                "y": y.copy(deep=True),
            }
        )

        if self.fit_error is not None:
            raise self.fit_error

        return self

    def forecast(
        self,
        *,
        steps: int,
        X: pd.DataFrame | None = None,
    ) -> list[float]:
        self.forecast_calls.append(
            {
                "steps": steps,
                "X": (
                    X.copy(deep=True)
                    if X is not None
                    else None
                ),
            }
        )

        if self.forecast_error is not None:
            raise self.forecast_error

        return list(self.predictions)