from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from eml_transformer.modeling.models.base import (
    BaseForecastModel, FloatArray
)


class RidgeForecastModel(BaseForecastModel):
    def __init__(
        self,
        *,
        alpha: float = 1.0,
        fit_intercept: bool = True,
        scale_features: bool = True,
        solver: str = "auto",
        max_iter: int | None = None,
        tolerance: float = 1e-4,
    ) -> None:
        self.alpha = alpha
        self.fit_intercept = fit_intercept
        self.scale_features = scale_features
        self.solver = solver
        self.max_iter = max_iter
        self.tolerance = tolerance

    @property
    def requires_exogenous(self) -> bool:
        return True

    def _fit_model(
        self,
        X: NDArray[np.float64],
        y: NDArray[np.float64],
    ) -> None:
        ridge = Ridge(
            alpha=self.alpha,
            fit_intercept=self.fit_intercept,
            solver=self.solver,
            max_iter=self.max_iter,
            tol=self.tolerance,
        )

        if self.scale_features:
            self.estimator_ = Pipeline(
                steps=[
                    ("scaler", StandardScaler()),
                    ("ridge", ridge),
                ]
            )
        else:
            self.estimator_ = ridge

        self.estimator_.fit(X, y)

    def _forecast_model(
        self,
        *,
        steps: int,
        X: FloatArray | None,
    ) -> FloatArray:
        if X is None:
            raise ValueError(
                "Ridge requires exogenous features"
            )

        predictions = self.estimator_.predict(X)

        return np.asarray(predictions, dtype=float)

    def _build_diagnostics(
        self,
        X: NDArray[np.float64],
        y: NDArray[np.float64],
    ) -> dict[str, Any]:
        ridge = self._ridge_estimator()

        coefficients = {
            str(feature): float(coefficient)
            for feature, coefficient in zip(
                self.feature_names_in_,
                np.ravel(ridge.coef_),
                strict=True,
            )
        }

        fitted = np.asarray(
            self.estimator_.predict(X),
            dtype=float,
        )
        residuals = y - fitted

        diagnostics: dict[str, Any] = {
            "alpha": float(self.alpha),
            "solver": self.solver,
            "fit_intercept": self.fit_intercept,
            "features_scaled": self.scale_features,
            "intercept": float(
                np.asarray(ridge.intercept_).item()
            ),
            "coefficients": coefficients,
            "coefficient_l1_norm": float(
                np.sum(np.abs(ridge.coef_))
            ),
            "coefficient_l2_norm": float(
                np.linalg.norm(ridge.coef_)
            ),
            "training_r_squared": float(
                self.estimator_.score(X, y)
            ),
            "residual_mean": float(
                np.mean(residuals)
            ),
            "residual_std": float(
                np.std(residuals, ddof=1)
            ),
            "residual_min": float(
                np.min(residuals)
            ),
            "residual_max": float(
                np.max(residuals)
            ),
        }

        iterations = getattr(ridge, "n_iter_", None)

        if iterations is not None:
            iteration_values = np.asarray(
                iterations
            ).ravel()

            diagnostics["iterations"] = [
                int(value)
                for value in iteration_values
            ]

        if self.scale_features:
            scaler = self.estimator_.named_steps[
                "scaler"
            ]

            diagnostics["feature_means"] = {
                str(feature): float(value)
                for feature, value in zip(
                    self.feature_names_in_,
                    scaler.mean_,
                    strict=True,
                )
            }
            diagnostics["feature_scales"] = {
                str(feature): float(value)
                for feature, value in zip(
                    self.feature_names_in_,
                    scaler.scale_,
                    strict=True,
                )
            }

        return diagnostics

    def _ridge_estimator(self) -> Ridge:
        if self.scale_features:
            return self.estimator_.named_steps["ridge"]

        return self.estimator_