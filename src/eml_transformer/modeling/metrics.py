from typing import Any

import numpy as np
from numpy.typing import ArrayLike
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
    r2_score,
)


def calculate_regression_metrics(
    actual: ArrayLike,
    predicted: ArrayLike,
) -> dict[str, float]:
    actual_array = np.asarray(actual, dtype=float)
    predicted_array = np.asarray(predicted, dtype=float)

    if actual_array.ndim != 1:
        raise ValueError("Actual values must be one-dimensional")

    if predicted_array.ndim != 1:
        raise ValueError("Predicted values must be one-dimensional")

    if len(actual_array) != len(predicted_array):
        raise ValueError(
            "Actual and predicted values must have equal lengths"
        )

    if len(actual_array) == 0:
        raise ValueError("Cannot calculate metrics on empty arrays")

    if not np.isfinite(actual_array).all():
        raise ValueError("Actual values contain NaN or infinity")

    if not np.isfinite(predicted_array).all():
        raise ValueError("Predicted values contain NaN or infinity")

    return {
        "mae": float(
            mean_absolute_error(actual_array, predicted_array)
        ),
        "rmse": float(
            mean_squared_error(
                actual_array,
                predicted_array,
            )
            ** 0.5
        ),
        "mape": float(
            mean_absolute_percentage_error(
                actual_array,
                predicted_array,
            )
        ),
        "r2": float(
            r2_score(actual_array, predicted_array)
        ),
    }