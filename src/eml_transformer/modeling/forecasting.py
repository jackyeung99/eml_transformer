from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from eml_transformer.modeling.artifacts import (
    ModelMetadata,
)
from eml_transformer.modeling.models.base import (
    BaseForecastModel,
)
from eml_transformer.utils.dates import (
    ensure_utc,
)


@dataclass(frozen=True, slots=True)
class GeneratedForecast:
    records: pd.DataFrame
    forecast_origin: datetime
    generated_at: datetime

    @property
    def records_written(self) -> int:
        return len(self.records)


def generate_forecast(
    model: BaseForecastModel,
    metadata: ModelMetadata,
    data: pd.DataFrame,
    *,
    timestamp_column: str,
    generated_at: datetime,
    forecast_steps: int,
    frequency: str,
    forecast_origin: datetime | None = None,
) -> GeneratedForecast:
    if data.empty:
        raise ValueError("Forecast input is empty")

    if forecast_steps <= 0:
        raise ValueError(
            "forecast_steps must be positive"
        )

    if timestamp_column not in data.columns:
        raise ValueError(
            f"Missing timestamp column {timestamp_column!r}"
        )

    prepared = data.copy()
    prepared[timestamp_column] = pd.to_datetime(
        prepared[timestamp_column],
        utc=True,
        errors="raise",
    )
    prepared = prepared.sort_values(timestamp_column)

    generated_at = ensure_utc(generated_at)

    origin = _resolve_forecast_origin(
        prepared,
        timestamp_column=timestamp_column,
        target=metadata.target,
        forecast_origin=forecast_origin,
    )

    if model.requires_exogenous:
        forecast_for, X_future = (
            _prepare_exogenous_forecast_input(
                prepared,
                timestamp_column=timestamp_column,
                features=metadata.features,
                forecast_origin=origin,
                forecast_steps=forecast_steps,
            )
        )
    else:
        forecast_for = _build_future_timestamps(
            forecast_origin=origin,
            forecast_steps=forecast_steps,
            frequency=frequency,
        )
        X_future = None

    predictions = model.forecast(
        steps=forecast_steps,
        X=X_future,
    )

    if len(predictions) != forecast_steps:
        raise ValueError(
            "Model returned an unexpected number of "
            f"predictions: expected {forecast_steps}, "
            f"received {len(predictions)}"
        )

    records = pd.DataFrame(
        {
            "forecast_id": [
                _build_forecast_id(
                    model_name=metadata.name,
                    model_version=metadata.model_version,
                    forecast_origin=origin,
                    forecast_for=timestamp,
                )
                for timestamp in forecast_for
            ],
            "model_name": metadata.name,
            "model_type": metadata.model_type,
            "model_version": metadata.model_version,
            "model_trained_at": metadata.trained_at,
            "generated_at": generated_at,
            "forecast_origin": origin,
            "forecast_for": forecast_for,
            "horizon": range(
                1,
                forecast_steps + 1,
            ),
            "predicted_value": predictions,
        }
    )

    return GeneratedForecast(
        records=records,
        forecast_origin=origin.to_pydatetime(),
        generated_at=generated_at,
    )

def _build_future_timestamps(
    *,
    forecast_origin: pd.Timestamp,
    forecast_steps: int,
    frequency: str,
) -> pd.DatetimeIndex:
    try:
        offset = pd.tseries.frequencies.to_offset(
            frequency
        )
    except ValueError as exc:
        raise ValueError(
            f"Invalid forecast frequency {frequency!r}"
        ) from exc

    first_forecast = forecast_origin + offset

    return pd.date_range(
        start=first_forecast,
        periods=forecast_steps,
        freq=offset,
    )

def _resolve_forecast_origin(
    data: pd.DataFrame,
    *,
    timestamp_column: str,
    target: str,
    forecast_origin: datetime | None,
) -> pd.Timestamp:
    if forecast_origin is not None:
        return pd.Timestamp(
            ensure_utc(forecast_origin)
        )

    if target not in data.columns:
        raise ValueError(
            "forecast_origin must be provided when the "
            f"target column {target!r} is unavailable"
        )

    observed = data.loc[
        data[target].notna(),
        timestamp_column,
    ]

    if observed.empty:
        raise ValueError(
            "Cannot infer forecast origin because no "
            "observed target values are available"
        )

    return observed.max()


def _prepare_exogenous_forecast_input(
    data: pd.DataFrame,
    *,
    timestamp_column: str,
    features: tuple[str, ...],
    forecast_origin: pd.Timestamp,
    forecast_steps: int,
) -> tuple[pd.Series, pd.DataFrame]:
    missing_features = [
        feature
        for feature in features
        if feature not in data.columns
    ]

    if missing_features:
        raise ValueError(
            "Forecast input is missing exogenous features: "
            f"{missing_features!r}"
        )

    future = data.loc[
        data[timestamp_column] > forecast_origin
    ].head(forecast_steps)

    if len(future) < forecast_steps:
        raise ValueError(
            "Not enough future exogenous rows are "
            f"available: required {forecast_steps}, "
            f"received {len(future)}"
        )

    X_future = future.loc[
        :,
        list(features),
    ]

    features_with_missing_values = [
        feature
        for feature in features
        if X_future[feature].isna().any()
    ]

    if features_with_missing_values:
        raise ValueError(
            "Future exogenous features contain missing "
            f"values: {features_with_missing_values!r}"
        )

    return (
        future[timestamp_column].reset_index(drop=True),
        X_future.reset_index(drop=True),
    )


def _build_forecast_id(
    *,
    model_name: str,
    model_version: str,
    forecast_origin: pd.Timestamp,
    forecast_for: pd.Timestamp,
) -> str:
    identity = "|".join(
        [
            model_name,
            model_version,
            forecast_origin.isoformat(),
            forecast_for.isoformat(),
        ]
    )

    return hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()