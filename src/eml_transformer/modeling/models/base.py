from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.utils.validation import check_is_fitted


FloatArray = NDArray[np.float64]


class BaseForecastModel(
    RegressorMixin,
    BaseEstimator,
    ABC,
):
    """
    Scikit-learn-compatible base class for forecasting models.

    Subclasses implement model-specific fitting, forecasting,
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
        """
        Fit the forecasting model.

        Parameters
        ----------
        X:
            Historical exogenous features. Must be provided when
            ``requires_exogenous`` is True.
        y:
            Historical target values.
        """
        y_values = self._validate_target(y)

        if self.requires_exogenous:
            X_values = self._validate_training_features(
                X,
                expected_rows=len(y_values),
            )
        else:
            self._validate_no_exogenous_features(X)

            X_values = None
            self.feature_names_in_ = np.asarray(
                [],
                dtype=object,
            )
            self.n_features_in_ = 0

        self.records_fitted_ = len(y_values)

        self._fit_model(
            X=X_values,
            y=y_values,
        )

        self.diagnostics_ = self._build_diagnostics(
            X=X_values,
            y=y_values,
        )
        self.is_fitted_ = True

        return self

    def forecast(
        self,
        *,
        steps: int,
        X: pd.DataFrame | None = None,
    ) -> FloatArray:
        """
        Generate a multi-step forecast.

        Parameters
        ----------
        steps:
            Number of future periods to forecast.
        X:
            Future exogenous features. The number of rows must
            match ``steps``.
        """
        check_is_fitted(self, "is_fitted_")

        if not isinstance(steps, int):
            raise TypeError("steps must be an integer")

        if steps <= 0:
            raise ValueError("steps must be positive")

        if self.requires_exogenous:
            X_values = self._validate_prediction_features(
                X,
                expected_rows=steps,
            )
        else:
            self._validate_no_exogenous_features(X)
            X_values = None

        predictions = self._forecast_model(
            steps=steps,
            X=X_values,
        )

        values = np.asarray(
            predictions,
            dtype=np.float64,
        ).reshape(-1)

        if len(values) != steps:
            raise ValueError(
                "Model returned an unexpected number of "
                f"forecasts: expected {steps}, "
                f"received {len(values)}"
            )

        if not np.isfinite(values).all():
            raise ValueError(
                "Model returned non-finite forecast values"
            )

        return values

    def get_diagnostics(self) -> dict[str, Any]:
        """Return a copy of the fitted model diagnostics."""
        check_is_fitted(self, "is_fitted_")
        return dict(self.diagnostics_)

    @abstractmethod
    def _fit_model(
        self,
        X: FloatArray | None,
        y: FloatArray,
    ) -> None:
        """Fit the model-specific estimator."""

    @abstractmethod
    def _forecast_model(
        self,
        *,
        steps: int,
        X: FloatArray | None,
    ) -> FloatArray:
        """Generate forecasts from the fitted model."""

    def _build_diagnostics(
        self,
        X: FloatArray | None,
        y: FloatArray,
    ) -> dict[str, Any]:
        """
        Return JSON-serializable model diagnostics.

        Subclasses can override this method when they have useful
        model-specific diagnostics.
        """
        return {}

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

        values = y.to_numpy(dtype=np.float64)

        if not np.isfinite(values).all():
            raise ValueError(
                "Target contains non-finite values"
            )

        return values

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

        self._validate_feature_frame(X)

        if X.empty:
            raise ValueError(
                "Exogenous feature data is empty"
            )

        if len(X) != expected_rows:
            raise ValueError(
                "Target and feature row counts do not match: "
                f"expected {expected_rows}, "
                f"received {len(X)}"
            )

        feature_names = self._get_feature_names(X)

        self.feature_names_in_ = np.asarray(
            feature_names,
            dtype=object,
        )
        self.n_features_in_ = X.shape[1]

        return self._to_feature_array(X)

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

        self._validate_feature_frame(X)

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
        received = self._get_feature_names(X)

        if received != expected:
            raise ValueError(
                "Future features do not match fitted "
                f"features. Expected {expected!r}, "
                f"received {received!r}"
            )

        return self._to_feature_array(X)

    @staticmethod
    def _validate_feature_frame(
        X: pd.DataFrame,
    ) -> None:
        if not isinstance(X, pd.DataFrame):
            raise TypeError(
                "X must be a pandas DataFrame"
            )

        if X.columns.has_duplicates:
            raise ValueError(
                "Feature names contain duplicates"
            )

        if X.shape[1] == 0:
            raise ValueError(
                "Feature data does not contain any columns"
            )

        if X.isna().any().any():
            raise ValueError(
                "Exogenous features contain missing values"
            )

    @staticmethod
    def _get_feature_names(
        X: pd.DataFrame,
    ) -> tuple[str, ...]:
        return tuple(
            str(column)
            for column in X.columns
        )

    @staticmethod
    def _to_feature_array(
        X: pd.DataFrame,
    ) -> FloatArray:
        try:
            values = X.to_numpy(dtype=np.float64)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "Exogenous features must be numeric"
            ) from error

        if not np.isfinite(values).all():
            raise ValueError(
                "Exogenous features contain non-finite values"
            )

        return values

    def _validate_no_exogenous_features(
        self,
        X: pd.DataFrame | None,
    ) -> None:
        if X is None:
            return

        if not isinstance(X, pd.DataFrame):
            raise TypeError(
                "X must be a pandas DataFrame or None"
            )

        if not X.empty:
            raise ValueError(
                f"{type(self).__name__} does not use "
                "exogenous features"
            )