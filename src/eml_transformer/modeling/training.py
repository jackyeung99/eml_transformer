from __future__ import annotations
from datetime import datetime, timedelta, timezone

from dataclasses import dataclass
from typing import Any
import pandas as pd
from eml_transformer.modeling.models.base import BaseForecastModel



from eml_transformer.modeling.artifacts import ModelMetadata
from eml_transformer.modeling.backtesting import split_latest_training_data
from eml_transformer.modeling.metrics import calculate_regression_metrics


@dataclass(frozen=True, slots=True)
class TrainedModel:
    model: BaseForecastModel

    features: tuple[str, ...]
    target: str

    records_used: int
    records_trained: int
    records_validated: int

    training_start: datetime
    training_end: datetime
    validation_start: datetime
    validation_end: datetime

    metrics: dict[str, float]
    diagnostics: dict[str, Any]


@dataclass(frozen=True, slots=True)
class TrainingDecision:
    should_train: bool
    reason: str


def train_model(
    model: BaseForecastModel,
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

    X_train = (
        split.training.loc[
            :,
            list(features),
        ]
        if model.requires_exogenous
        else None
    )

    X_validation = (
        split.validation.loc[
            :,
            list(features),
        ]
        if model.requires_exogenous
        else None
    )

    y_train =  split.training[target]
    y_validation = split.validation[target]

    model.fit(X_train, y_train)

    predictions = model.forecast(
        steps=len(y_validation),
        X=X_validation,
    )

    metrics = calculate_regression_metrics(
        y_validation,
        predictions,
    )

    # Refit the persisted model using the entire lookback window.
    full_window = pd.concat(
        [split.training, split.validation],
        ignore_index=True,
    )

    X_full = (
        full_window.loc[:, list(features)]
        if model.requires_exogenous
        else None
    )

    model.fit(
        X_full,
        full_window.loc[:, target],
    )
    
    return TrainedModel(
        model=model,
        features=features,
        target=target,

        records_used=len(full_window),
        records_trained=len(split.training),
        records_validated=len(split.validation),

        training_start= split.training_start,
        training_end = split.training_end,
        validation_start= split.validation_start,
        validation_end=split.validation_end,

        metrics=metrics,
        diagnostics=model.diagnostics_
    )


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