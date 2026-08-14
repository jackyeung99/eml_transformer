import numpy as np
from numpy.typing import NDArray
from sklearn.linear_model import LinearRegression


from eml_transformer.modeling.models.base import BaseForecastModel

class LinearForecastModel(BaseForecastModel):
    def __init__(
        self,
        *,
        fit_intercept: bool = True,
        positive: bool = False,
    ) -> None:
        self.fit_intercept = fit_intercept
        self.positive = positive

    def _fit_model(
        self,
        X: NDArray[np.float64],
        y: NDArray[np.float64],
    ) -> None:
        self.estimator_ = LinearRegression(
            fit_intercept=self.fit_intercept,
            positive=self.positive,
        )
        self.estimator_.fit(X, y)

    def _predict_model(
        self,
        X: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        return self.estimator_.predict(X)

    def _build_diagnostics(
        self,
        X: NDArray[np.float64],
        y: NDArray[np.float64],
    ) -> dict[str, Any]:
        fitted = self.estimator_.predict(X)
        residuals = y - fitted

        coefficients = {
            str(feature): float(coefficient)
            for feature, coefficient in zip(
                self.feature_names_in_,
                self.estimator_.coef_,
                strict=True,
            )
        }

        return {
            "intercept": float(self.estimator_.intercept_),
            "coefficients": coefficients,
            "residual_mean": float(np.mean(residuals)),
            "residual_std": float(
                np.std(residuals, ddof=1)
            ),
            "residual_min": float(np.min(residuals)),
            "residual_max": float(np.max(residuals)),
            "training_r_squared": float(
                self.estimator_.score(X, y)
            ),
        }