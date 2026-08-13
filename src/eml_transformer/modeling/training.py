

from __future__ import annotations
from datetime import datetime, timedelta, timezone

from dataclasses import dataclass

import pandas as pd
from sklearn.base import BaseEstimator


from eml_transformer.modeling.artifacts import ModelMetadata
from eml_transformer.modeling.backtesting import split_latest_training_data
from eml_transformer.modeling.metrics import calculate_regression_metrics


@dataclass(frozen=True, slots=True)
class TrainedModel:
    model: BaseEstimator
    records_used: int
    records_trained: int
    records_validated: int
    metrics: dict[str, float]
    features: tuple[str, ...]
    target: str


def train_model(
    model: BaseEstimator,
    data: pd.DataFrame,
    *,
    features: tuple[str, ...],
    target: str,
    timestamp_column: str,
    lookback_days: int,
    validation_days: int,
) -> TrainedModel:
    required_columns = [
        timestamp_column,
        *features,
        target,
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in data.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing training columns: {missing_columns}"
        )

    prepared = (
        data.loc[:, required_columns]
        .dropna()
        .sort_values(timestamp_column)
    )

    split = split_latest_training_data(
        prepared,
        timestamp_column=timestamp_column,
        lookback_days=lookback_days,
        validation_days=validation_days,
    )

    X_train = split.training.loc[:, features]
    y_train = split.training.loc[:, target]

    X_validation = split.validation.loc[:, features]
    y_validation = split.validation.loc[:, target]

    model.fit(X_train, y_train)

    predictions = model.predict(X_validation)

    metrics = calculate_regression_metrics(
        y_validation,
        predictions,
    )

    # Refit the persisted model using the entire lookback window.
    full_window = pd.concat(
        [split.training, split.validation],
        ignore_index=True,
    )

    model.fit(
        full_window.loc[:, features],
        full_window.loc[:, target],
    )

    return TrainedModel(
        model=model,
        features=features,
        target=target,
        records_used=len(full_window),
        records_trained=len(split.training),
        records_validated=len(split.validation),
        metrics=metrics,
    )
@dataclass(frozen=True, slots=True)
class TrainingDecision:
    should_train: bool
    reason: str


def should_train(
    metadata: ModelMetadata | None,
    *,
    retrain_after_hours: int | None,
    now: datetime | None = None,
) -> TrainingDecision:
    if metadata is None:
        return TrainingDecision(
            should_train=True,
            reason="No existing model was found",
        )

    if retrain_after_hours is None:
        return TrainingDecision(
            should_train=False,
            reason="An existing model is available",
        )

    now = now or datetime.now(timezone.utc)
    retrain_at = metadata.trained_at + timedelta(
        hours=retrain_after_hours
    )

    if now >= retrain_at:
        return TrainingDecision(
            should_train=True,
            reason="Existing model has expired",
        )

    return TrainingDecision(
        should_train=False,
        reason="Existing model is still current",
    )