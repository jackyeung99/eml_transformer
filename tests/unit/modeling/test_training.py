from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

import eml_transformer.modeling.training as training_module
from eml_transformer.modeling.training import (
    TrainingDecision,
    should_train,
    train_model,
)


UTC = timezone.utc

NOW = datetime(
    2026,
    1,
    15,
    12,
    0,
    tzinfo=UTC,
)


class FakeForecastModel:
    def __init__(
        self,
        *,
        requires_exogenous: bool,
        predictions: list[float] | None = None,
    ) -> None:
        self.requires_exogenous = requires_exogenous
        self.predictions = predictions or []

        self.fit_calls: list[
            tuple[
                pd.DataFrame | None,
                pd.Series,
            ]
        ] = []
        self.forecast_calls: list[
            dict[str, Any]
        ] = []

        self.diagnostics_ = {
            "fake_diagnostic": 123,
        }

    def fit(
        self,
        X: pd.DataFrame | None,
        y: pd.Series,
    ) -> FakeForecastModel:
        self.fit_calls.append(
            (
                (
                    X.copy(deep=True)
                    if X is not None
                    else None
                ),
                y.copy(deep=True),
            )
        )

        return self

    def forecast(
        self,
        *,
        steps: int,
        X: pd.DataFrame | None,
    ) -> list[float]:
        self.forecast_calls.append(
            {
                "steps": steps,
                "X": (
                    X.copy(deep=True)
                    if X is not None
                    else None
                ),
            }
        )

        return self.predictions


def make_training_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "observed_at": pd.to_datetime(
                [
                    "2026-01-01T00:00:00Z",
                    "2026-01-02T00:00:00Z",
                    "2026-01-03T00:00:00Z",
                    "2026-01-04T00:00:00Z",
                ]
            ),
            "feature_1": [
                1.0,
                2.0,
                3.0,
                4.0,
            ],
            "feature_2": [
                10.0,
                20.0,
                30.0,
                40.0,
            ],
            "target": [
                100.0,
                101.0,
                102.0,
                103.0,
            ],
        }
    )


def make_split(
    data: pd.DataFrame,
) -> SimpleNamespace:
    training = data.iloc[:2].copy()
    validation = data.iloc[2:].copy()

    return SimpleNamespace(
        training=training,
        validation=validation,
        training_start=training[
            "observed_at"
        ].min(),
        training_end=training[
            "observed_at"
        ].max(),
        validation_start=validation[
            "observed_at"
        ].min(),
        validation_end=validation[
            "observed_at"
        ].max(),
    )


def test_train_model_with_exogenous_features(
    monkeypatch: pytest.MonkeyPatch,
):
    data = make_training_data()

    model = FakeForecastModel(
        requires_exogenous=True,
        predictions=[
            101.5,
            103.5,
        ],
    )

    split_calls: list[
        dict[str, Any]
    ] = []

    def fake_split_latest_training_data(
        prepared: pd.DataFrame,
        **kwargs: Any,
    ) -> SimpleNamespace:
        split_calls.append(
            {
                "data": prepared.copy(deep=True),
                **kwargs,
            }
        )

        return make_split(prepared)

    monkeypatch.setattr(
        training_module,
        "split_latest_training_data",
        fake_split_latest_training_data,
    )
    monkeypatch.setattr(
        training_module,
        "calculate_regression_metrics",
        lambda actual, predicted: {
            "mae": 0.5,
            "rmse": 0.5,
        },
    )

    trained = train_model(
        model,
        data,
        features=(
            "feature_1",
            "feature_2",
        ),
        target="target",
        timestamp_column="observed_at",
        lookback_days=30,
        validation_days=2,
    )

    assert trained.model is model
    assert trained.features == (
        "feature_1",
        "feature_2",
    )
    assert trained.target == "target"
    assert trained.records_used == 4
    assert trained.records_trained == 2
    assert trained.records_validated == 2
    assert trained.metrics == {
        "mae": 0.5,
        "rmse": 0.5,
    }
    assert trained.diagnostics == {
        "fake_diagnostic": 123,
    }

    assert len(split_calls) == 1
    assert split_calls[0][
        "timestamp_column"
    ] == "observed_at"
    assert split_calls[0][
        "lookback_days"
    ] == 30
    assert split_calls[0][
        "validation_days"
    ] == 2

    # Fit once on training data and again on the complete window.
    assert len(model.fit_calls) == 2

    first_X, first_y = model.fit_calls[0]

    assert first_X is not None
    assert first_X.columns.tolist() == [
        "feature_1",
        "feature_2",
    ]
    assert first_X["feature_1"].tolist() == [
        1.0,
        2.0,
    ]
    assert first_y.tolist() == [
        100.0,
        101.0,
    ]

    full_X, full_y = model.fit_calls[1]

    assert full_X is not None
    assert len(full_X) == 4
    assert full_y.tolist() == [
        100.0,
        101.0,
        102.0,
        103.0,
    ]

    assert len(model.forecast_calls) == 1
    assert model.forecast_calls[0]["steps"] == 2

    forecast_X = model.forecast_calls[0]["X"]

    assert forecast_X is not None
    assert forecast_X["feature_1"].tolist() == [
        3.0,
        4.0,
    ]


def test_train_model_without_exogenous_features(
    monkeypatch: pytest.MonkeyPatch,
):
    data = make_training_data()

    model = FakeForecastModel(
        requires_exogenous=False,
        predictions=[
            101.5,
            103.5,
        ],
    )

    monkeypatch.setattr(
        training_module,
        "split_latest_training_data",
        lambda prepared, **kwargs: make_split(
            prepared
        ),
    )
    monkeypatch.setattr(
        training_module,
        "calculate_regression_metrics",
        lambda actual, predicted: {
            "mae": 0.5,
        },
    )

    trained = train_model(
        model,
        data,
        features=(),
        target="target",
        timestamp_column="observed_at",
        lookback_days=30,
        validation_days=2,
    )

    assert trained.records_trained == 2
    assert trained.records_validated == 2

    assert len(model.fit_calls) == 2
    assert model.fit_calls[0][0] is None
    assert model.fit_calls[1][0] is None

    assert model.forecast_calls == [
        {
            "steps": 2,
            "X": None,
        }
    ]


def test_train_model_rejects_missing_columns():
    data = make_training_data().drop(
        columns=["feature_2"]
    )

    model = FakeForecastModel(
        requires_exogenous=True,
    )

    with pytest.raises(
        ValueError,
        match="Missing training columns",
    ):
        train_model(
            model,
            data,
            features=(
                "feature_1",
                "feature_2",
            ),
            target="target",
            timestamp_column="observed_at",
            lookback_days=30,
            validation_days=2,
        )

    assert model.fit_calls == []
    assert model.forecast_calls == []


def test_train_model_drops_missing_rows_and_sorts(
    monkeypatch: pytest.MonkeyPatch,
):
    data = make_training_data()

    data.loc[1, "feature_1"] = None

    # Reverse the input to verify chronological sorting.
    data = data.iloc[::-1].reset_index(
        drop=True
    )

    prepared_frames: list[
        pd.DataFrame
    ] = []

    def capture_prepared_data(
        prepared: pd.DataFrame,
        **kwargs: Any,
    ) -> SimpleNamespace:
        prepared_frames.append(
            prepared.copy(deep=True)
        )

        # Use one training and two validation rows.
        training = prepared.iloc[:1].copy()
        validation = prepared.iloc[1:].copy()

        return SimpleNamespace(
            training=training,
            validation=validation,
            training_start=training[
                "observed_at"
            ].min(),
            training_end=training[
                "observed_at"
            ].max(),
            validation_start=validation[
                "observed_at"
            ].min(),
            validation_end=validation[
                "observed_at"
            ].max(),
        )

    monkeypatch.setattr(
        training_module,
        "split_latest_training_data",
        capture_prepared_data,
    )
    monkeypatch.setattr(
        training_module,
        "calculate_regression_metrics",
        lambda actual, predicted: {
            "mae": 0.0,
        },
    )

    model = FakeForecastModel(
        requires_exogenous=True,
        predictions=[
            102.0,
            103.0,
        ],
    )

    train_model(
        model,
        data,
        features=(
            "feature_1",
            "feature_2",
        ),
        target="target",
        timestamp_column="observed_at",
        lookback_days=30,
        validation_days=2,
    )

    prepared = prepared_frames[0]

    assert len(prepared) == 3
    assert prepared["observed_at"].is_monotonic_increasing
    assert prepared["feature_1"].isna().sum() == 0


@pytest.mark.parametrize(
    (
        "metadata",
        "retrain_after_hours",
        "expected_should_train",
        "expected_reason",
    ),
    [
        (
            None,
            24,
            True,
            "No existing model was found",
        ),
        (
            SimpleNamespace(
                trained_at=NOW - timedelta(hours=1),
            ),
            None,
            False,
            "An existing model is available",
        ),
        (
            SimpleNamespace(
                trained_at=NOW - timedelta(hours=25),
            ),
            24,
            True,
            "Existing model has expired",
        ),
        (
            SimpleNamespace(
                trained_at=NOW - timedelta(hours=23),
            ),
            24,
            False,
            "Existing model is still current",
        ),
    ],
)
def test_should_train_decisions(
    metadata,
    retrain_after_hours,
    expected_should_train,
    expected_reason,
):
    decision = should_train(
        metadata=metadata,
        retrain_after_hours=retrain_after_hours,
        now=NOW,
    )

    assert decision == TrainingDecision(
        should_train=expected_should_train,
        reason=expected_reason,
    )


def test_should_train_at_exact_expiration():
    metadata = SimpleNamespace(
        trained_at=NOW - timedelta(hours=24),
    )

    decision = should_train(
        metadata=metadata,
        retrain_after_hours=24,
        now=NOW,
    )

    assert decision.should_train is True
    assert decision.reason == (
        "Existing model has expired"
    )