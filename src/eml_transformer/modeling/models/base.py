from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.utils.validation import (
    check_array,
    check_is_fitted,
    check_X_y,
)

FloatArray = NDArray[np.float64]

class BaseForecastModel(
    RegressorMixin,
    BaseEstimator,
    ABC,
):
    """
    Scikit-learn-compatible base class for forecasting models.

    Subclasses implement the model-specific fitting, prediction,
    and diagnostic behavior.
    """

    @property
    @abstractmethod
    def requires_exogenous(self) -> bool:
        """Whether the model requires exogenous features."""

    def fit(
        self,
        X: pd.DataFrame | None,
        y: pd.Series,
    ):
        y_values = self._validate_target(y)

        if self.requires_exogenous:
            X_values = self._validate_training_features(
                X,
                expected_rows=len(y_values),
            )
        else:
            if X is not None and not X.empty:
                raise ValueError(
                    f"{type(self).__name__} does not use "
                    "exogenous features"
                )

            X_values = None
            self.feature_names_in_ = np.asarray(
                [],
                dtype=object,
            )
            self.n_features_in_ = 0

        self.records_fitted_ = len(y_values)

        self._fit_model(X_values, y_values)

        self.diagnostics_ = self._build_diagnostics(
            X_values,
            y_values,
        )
        self.is_fitted_ = True

        return self

    
    def forecast(
        self,
        *,
        steps: int,
        X: pd.DataFrame | None = None,
    ) -> FloatArray:
        check_is_fitted(self, "is_fitted_")

        if steps <= 0:
            raise ValueError("steps must be positive")

        if self.requires_exogenous:
            X_values = self._validate_prediction_features(
                X,
                expected_rows=steps,
            )
        else:
            if X is not None and not X.empty:
                raise ValueError(
                    f"{type(self).__name__} does not use "
                    "exogenous features"
                )

            X_values = None

        predictions = self._forecast_model(
            steps=steps,
            X=X_values,
        )

        values = np.asarray(
            predictions,
            dtype=float,
        ).reshape(-1)

        if len(values) != steps:
            raise ValueError(
                "Model returned an unexpected number of "
                f"forecasts: expected {steps}, "
                f"received {len(values)}"
            )

        return values

    def get_diagnostics(self) -> dict[str, Any]:
        check_is_fitted(self, "is_fitted_")
        return dict(self.diagnostics_)

    @abstractmethod
    def _fit_model(
        self,
        X: NDArray[np.float64],
        y: NDArray[np.float64],
    ) -> None:
        """Fit the model-specific estimator."""

    def _build_diagnostics(
        self,
        X: NDArray[np.float64],
        y: NDArray[np.float64],
    ) -> dict[str, Any]:
        """
        Return model-specific, JSON-serializable diagnostics.

        Subclasses can override this when they have useful
        diagnostics to report.
        """
        return {}

    @staticmethod
    def _get_feature_names(
        X: pd.DataFrame,
    ) -> tuple[str, ...]:
        if not isinstance(X, pd.DataFrame):
            raise TypeError(
                "Forecast models require X to be a DataFrame "
                "so feature names can be preserved"
            )

        if X.columns.has_duplicates:
            raise ValueError(
                "Forecast features cannot contain duplicate names"
            )

        return tuple(str(column) for column in X.columns)

    
    @staticmethod
    def _validate_target(
        y: pd.Series,
    ) -> FloatArray:
        if not isinstance(y, pd.Series):
            raise TypeError("y must be a pandas Series")

        if y.empty:
            raise ValueError("Target is empty")

        if y.isna().any():
            raise ValueError(
                "Target contains missing values"
            )

        return y.to_numpy(dtype=float)

    def _validate_training_features(
        self,
        X: pd.DataFrame | None,
        *,
        expected_rows: int,
    ) -> FloatArray:
        if X is None:
            raise ValueError(
                f"{type(self).__name__} requires "
                "exogenous features"
            )

        if not isinstance(X, pd.DataFrame):
            raise TypeError(
                "X must be a pandas DataFrame"
            )

        if X.empty:
            raise ValueError(
                "Exogenous feature data is empty"
            )

        if len(X) != expected_rows:
            raise ValueError(
                "Target and feature row counts do not match"
            )

        if X.columns.has_duplicates:
            raise ValueError(
                "Feature names contain duplicates"
            )

        if X.isna().any().any():
            raise ValueError(
                "Exogenous features contain missing values"
            )

        self.feature_names_in_ = np.asarray(
            [str(column) for column in X.columns],
            dtype=object,
        )
        self.n_features_in_ = X.shape[1]

        return X.to_numpy(dtype=float)

    def _validate_prediction_features(
        self,
        X: pd.DataFrame | None,
        *,
        expected_rows: int,
    ) -> FloatArray:
        if X is None:
            raise ValueError(
                f"{type(self).__name__} requires future "
                "exogenous features"
            )

        if len(X) != expected_rows:
            raise ValueError(
                "Future feature row count must match "
                f"forecast steps: expected {expected_rows}, "
                f"received {len(X)}"
            )

        expected = tuple(
            str(feature)
            for feature in self.feature_names_in_
        )
        received = tuple(str(column) for column in X.columns)

        if received != expected:
            raise ValueError(
                "Future features do not match fitted "
                f"features. Expected {expected!r}, "
                f"received {received!r}"
            )

        if X.isna().any().any():
            raise ValueError(
                "Future exogenous features contain "
                "missing values"
            )

        return X.to_numpy(dtype=float)