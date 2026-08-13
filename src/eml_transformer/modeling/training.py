

from __future__ import annotations
from datetime import datetime, timedelta, timezone

from dataclasses import dataclass

import pandas as pd
from sklearn.base import RegressorMixin
from sklearn.metrics import mean_absolute_error


from eml_transformer.modeling.artifacts import ModelMetadata



@dataclass(slots=True)
class TrainedModel:
    model: RegressorMixin
    metrics: dict[str, float]


def train_model(
    model: RegressorMixin,
    data: pd.DataFrame,
    *,
    features: tuple[str, ...],
    target: str,
) -> TrainedModel:

    return TrainedModel(
        model=model,
        metrics=metrics,
    )

def should_train(
    metadata: ModelMetadata | None,
    *,
    retrain_after: timedelta | None,
    force: bool = False,
) -> bool:
    if force:
        return True

    if metadata is None:
        return True

    if retrain_after is None:
        return False

    return (
        datetime.now(timezone.utc) - metadata.trained_at
        >= retrain_after
    )