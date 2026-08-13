from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.utils.validation import check_is_fitted


# uses scikit learn style
class CustomLoadModel(RegressorMixin, BaseEstimator):
    def __init__(
        self,
        *,
        daily_weight: float = 0.7,
        weekly_weight: float = 0.3,
    ) -> None:
        self.daily_weight = daily_weight
        self.weekly_weight = weekly_weight

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
    ) -> "CustomLoadModel":
        self.feature_names_in_ = np.asarray(X.columns)
        self.n_features_in_ = X.shape[1]
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        check_is_fitted(self, "is_fitted_")

        return (
            self.daily_weight * X["actual_load_lag_24"]
            + self.weekly_weight * X["actual_load_lag_168"]
        ).to_numpy()