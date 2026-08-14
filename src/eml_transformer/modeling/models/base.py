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

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
    ) -> BaseForecastModel:
        feature_names = self._get_feature_names(X)

        X_checked, y_checked = check_X_y(
            X,
            y,
            ensure_2d=True,
            y_numeric=True,
        )

        self.feature_names_in_ = np.asarray(
            feature_names,
            dtype=object,
        )
        self.n_features_in_ = X_checked.shape[1]
        self.records_fitted_ = X_checked.shape[0]

        self._fit_model(X_checked, y_checked)

        self.diagnostics_ = self._build_diagnostics(
            X_checked,
            y_checked,
        )
        self.is_fitted_ = True

        return self

    def predict(
        self,
        X: pd.DataFrame,
    ) -> NDArray[np.float64]:
        check_is_fitted(self, "is_fitted_")

        self._validate_prediction_features(X)

        X_checked = check_array(
            X,
            ensure_2d=True,
        )

        predictions = self._predict_model(X_checked)

        return np.asarray(
            predictions,
            dtype=float,
        )

    def forecast(
        self,
        X: pd.DataFrame,
    ) -> NDArray[np.float64]:
        """Domain-friendly alias for predict."""
        return self.predict(X)

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

    @abstractmethod
    def _predict_model(
        self,
        X: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Generate predictions with the fitted estimator."""

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

    def _validate_prediction_features(
        self,
        X: pd.DataFrame,
    ) -> None:
        if not isinstance(X, pd.DataFrame):
            raise TypeError(
                "Forecast models require X to be a DataFrame"
            )

        expected = tuple(
            str(feature)
            for feature in self.feature_names_in_
        )
        received = tuple(str(column) for column in X.columns)

        if received != expected:
            raise ValueError(
                "Forecast features do not match the fitted "
                "feature order. "
                f"Expected {expected!r}, received {received!r}"
            )