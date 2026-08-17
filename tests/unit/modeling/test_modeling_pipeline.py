from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

import eml_transformer.modeling.pipeline as pipeline_module
from eml_transformer.modeling.pipeline import (
    ModelingPipeline,
)
from eml_transformer.modeling.training import (
    TrainingDecision,
)


UTC = timezone.utc

TRAINED_AT = datetime(
    2026,
    1,
    15,
    12,
    0,
    tzinfo=UTC,
)
FORECAST_ORIGIN = datetime(
    2026,
    1,
    16,
    0,
    0,
    tzinfo=UTC,
)
GENERATED_AT = datetime(
    2026,
    1,
    16,
    0,
    5,
    tzinfo=UTC,
)


def make_model_definition(
    **overrides: Any,
) -> SimpleNamespace:
    values = {
        "name": "miso_load_ridge",
        "model_type": "ridge",
        "training_input": (
            "gold:load_forecasting:datasets"
        ),
        "forecast_input": (
            "gold:load_forecasting:datasets"
        ),
        "model_output": "miso_load_ridge",
        "forecast_output": (
            "gold:miso_load_ridge:forecasts"
        ),
        "target": "actual_load",
        "features": (
            "hour",
            "actual_load_lag_24",
        ),
        "retrain_after_hours": 168,
        "hyper_parameters": {
            "alpha": 1.0,
        },
        "training_settings": {
            "timestamp_column": "observed_at",
            "lookback_days": 730,
            "validation_days": 14,
        },
        "forecast_settings": {
            "timestamp_column": "observed_at",
            "forecast_steps": 2,
            "frequency": "1h",
        },
    }
    values.update(overrides)

    return SimpleNamespace(**values)


def make_training_data() -> pd.DataFrame:
    observed_at = pd.date_range(
        "2025-01-01",
        periods=10,
        freq="h",
        tz="UTC",
    )

    return pd.DataFrame(
        {
            "observed_at": observed_at,
            "hour": observed_at.hour,
            "actual_load_lag_24": [
                float(value)
                for value in range(100, 110)
            ],
            "actual_load": [
                float(value)
                for value in range(101, 111)
            ],
        }
    )


def make_forecast_data() -> pd.DataFrame:
    observed_at = pd.date_range(
        "2026-01-15",
        periods=4,
        freq="h",
        tz="UTC",
    )

    return pd.DataFrame(
        {
            "observed_at": observed_at,
            "hour": observed_at.hour,
            "actual_load_lag_24": [
                100.0,
                101.0,
                102.0,
                103.0,
            ],
            "actual_load": [
                101.0,
                102.0,
                103.0,
                104.0,
            ],
        }
    )


def test_train_skips_when_training_is_not_due(
    monkeypatch: pytest.MonkeyPatch,
    storage,
    paths,
):
    definition = make_model_definition()

    existing_metadata = SimpleNamespace(
        trained_at=TRAINED_AT,
    )

    storage.read_model_metadata = (
        lambda path: existing_metadata
    )

    monkeypatch.setattr(
        pipeline_module,
        "should_train",
        lambda **kwargs: TrainingDecision(
            should_train=False,
            reason="Model is still current",
        ),
    )

    pipeline = ModelingPipeline(
        storage=storage,
        paths=paths,
    )

    result = pipeline.train(definition)

    assert result.status == "skipped"
    assert result.name == definition.name
    assert result.reason == "Model is still current"
    assert result.model_ref == definition.model_output
    assert result.trained_at == TRAINED_AT
    assert result.records_read == 0


def test_train_skips_empty_dataset(
    monkeypatch: pytest.MonkeyPatch,
    storage,
    paths,
):
    definition = make_model_definition()

    storage.read_model_metadata = (
        lambda path: None
    )

    monkeypatch.setattr(
        pipeline_module,
        "should_train",
        lambda **kwargs: TrainingDecision(
            should_train=True,
            reason="No existing model",
        ),
    )

    pipeline = ModelingPipeline(
        storage=storage,
        paths=paths,
    )

    result = pipeline.train(definition)

    assert result.status == "skipped"
    assert result.reason == (
        "Training dataset is empty"
    )
    assert result.records_read == 0
    assert result.model_ref == definition.model_output


def test_train_creates_and_stores_model(
    monkeypatch: pytest.MonkeyPatch,
    storage,
    paths,
):
    definition = make_model_definition()
    training_data = make_training_data()

    storage.write_dataframe(
        definition.training_input,
        training_data,
    )

    storage.read_model_metadata = (
        lambda path: None
    )

    stored_models: list[
        tuple[str, Any, Any]
    ] = []

    storage.write_model = (
        lambda path, model, metadata: (
            stored_models.append(
                (
                    path,
                    model,
                    metadata,
                )
            )
        )
    )

    fake_model = object()
    trained_model = object()

    trained = SimpleNamespace(
        model=trained_model,
        features=definition.features,
        target=definition.target,
        records_used=10,
        records_trained=8,
        records_validated=2,
        metrics={
            "mae": 1.5,
            "rmse": 2.0,
        },
        diagnostics={
            "coefficients": {
                "hour": 0.5,
            }
        },
        training_start=datetime(
            2025,
            1,
            1,
            tzinfo=UTC,
        ),
        training_end=datetime(
            2025,
            1,
            8,
            tzinfo=UTC,
        ),
        validation_start=datetime(
            2025,
            1,
            9,
            tzinfo=UTC,
        ),
        validation_end=datetime(
            2025,
            1,
            10,
            tzinfo=UTC,
        ),
    )

    monkeypatch.setattr(
        pipeline_module,
        "should_train",
        lambda **kwargs: TrainingDecision(
            should_train=True,
            reason="No existing model",
        ),
    )
    monkeypatch.setattr(
        pipeline_module,
        "create_model",
        lambda model_type, settings: fake_model,
    )
    monkeypatch.setattr(
        pipeline_module,
        "train_model",
        lambda model, data, **kwargs: trained,
    )
    monkeypatch.setattr(
        pipeline_module,
        "utc_now",
        lambda: TRAINED_AT,
    )
    monkeypatch.setattr(
        pipeline_module,
        "build_model_version",
        lambda trained_at: "20260115T120000Z",
    )

    pipeline = ModelingPipeline(
        storage=storage,
        paths=paths,
    )

    result = pipeline.train(definition)

    assert result.status == "success"
    assert result.name == definition.name
    assert result.reason == "No existing model"
    assert result.records_read == 10
    assert result.records_trained == 8
    assert result.records_validated == 2
    assert result.metrics == {
        "mae": 1.5,
        "rmse": 2.0,
    }
    assert result.trained_at == TRAINED_AT

    assert len(stored_models) == 1

    model_path, saved_model, metadata = (
        stored_models[0]
    )

    assert model_path == paths.model(
        definition.model_output
    )
    assert saved_model is trained_model

    assert metadata.name == definition.name
    assert metadata.model_type == "ridge"
    assert metadata.model_version == (
        "20260115T120000Z"
    )
    assert metadata.features == definition.features
    assert metadata.target == definition.target
    assert metadata.records_used == 10
    assert metadata.records_trained == 8
    assert metadata.records_validated == 2
    assert metadata.metrics["mae"] == 1.5


def test_train_force_bypasses_training_decision(
    monkeypatch: pytest.MonkeyPatch,
    storage,
    paths,
):
    definition = make_model_definition()
    training_data = make_training_data()

    storage.write_dataframe(
        definition.training_input,
        training_data,
    )

    storage.read_model_metadata = (
        lambda path: SimpleNamespace(
            trained_at=TRAINED_AT,
        )
    )
    storage.write_model = (
        lambda path, model, metadata: None
    )

    def should_not_be_called(
        **kwargs: Any,
    ) -> TrainingDecision:
        raise AssertionError(
            "should_train should not be called "
            "when force=True"
        )

    monkeypatch.setattr(
        pipeline_module,
        "should_train",
        should_not_be_called,
    )
    monkeypatch.setattr(
        pipeline_module,
        "create_model",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        pipeline_module,
        "train_model",
        lambda *args, **kwargs: SimpleNamespace(
            model=object(),
            features=definition.features,
            target=definition.target,
            records_used=10,
            records_trained=8,
            records_validated=2,
            metrics={},
            diagnostics={},
            training_start=None,
            training_end=None,
            validation_start=None,
            validation_end=None,
        ),
    )
    monkeypatch.setattr(
        pipeline_module,
        "utc_now",
        lambda: TRAINED_AT,
    )
    monkeypatch.setattr(
        pipeline_module,
        "build_model_version",
        lambda trained_at: "forced-version",
    )

    pipeline = ModelingPipeline(
        storage=storage,
        paths=paths,
    )

    result = pipeline.train(
        definition,
        force=True,
    )

    assert result.status == "success"
    assert result.reason == "Training was forced"


def test_train_returns_failure_when_training_raises(
    monkeypatch: pytest.MonkeyPatch,
    storage,
    paths,
):
    definition = make_model_definition()
    training_data = make_training_data()

    storage.write_dataframe(
        definition.training_input,
        training_data,
    )

    storage.read_model_metadata = (
        lambda path: None
    )

    monkeypatch.setattr(
        pipeline_module,
        "should_train",
        lambda **kwargs: TrainingDecision(
            should_train=True,
            reason="No existing model",
        ),
    )

    def raise_training_error(
        *args: Any,
        **kwargs: Any,
    ) -> None:
        raise RuntimeError("Training exploded")

    monkeypatch.setattr(
        pipeline_module,
        "create_model",
        raise_training_error,
    )

    pipeline = ModelingPipeline(
        storage=storage,
        paths=paths,
    )

    result = pipeline.train(definition)

    assert result.status == "failure"
    assert result.reason == (
        "Training raised an exception"
    )
    assert result.error == "Training exploded"
    assert result.records_read == 10
    assert result.model_ref == definition.model_output


def test_forecast_skips_empty_input(
    storage,
    paths,
):
    definition = make_model_definition()

    storage.read_model = (
        lambda path: (
            object(),
            SimpleNamespace(
                model_version="model-v1",
            ),
        )
    )

    pipeline = ModelingPipeline(
        storage=storage,
        paths=paths,
    )

    result = pipeline.forecast(definition)

    assert result.status == "skipped"
    assert result.reason == (
        "Forecast input is empty"
    )
    assert result.records_read == 0
    assert result.records_written == 0
    assert result.model_ref == definition.model_output
    assert result.forecast_ref == (
        definition.forecast_output
    )


def test_forecast_generates_and_stores_records(
    monkeypatch: pytest.MonkeyPatch,
    storage,
    paths,
):
    definition = make_model_definition()
    forecast_data = make_forecast_data()

    storage.write_dataframe(
        definition.forecast_input,
        forecast_data,
    )

    fake_model = object()
    metadata = SimpleNamespace(
        model_version="model-v1",
    )

    storage.read_model = (
        lambda path: (
            fake_model,
            metadata,
        )
    )

    forecast_records = pd.DataFrame(
        {
            "forecast_id": [
                "forecast-1",
                "forecast-2",
            ],
            "model_name": [
                definition.name,
                definition.name,
            ],
            "model_version": [
                "model-v1",
                "model-v1",
            ],
            "forecast_origin": [
                FORECAST_ORIGIN,
                FORECAST_ORIGIN,
            ],
            "generated_at": [
                GENERATED_AT,
                GENERATED_AT,
            ],
            "target_time": [
                datetime(
                    2026,
                    1,
                    16,
                    1,
                    tzinfo=UTC,
                ),
                datetime(
                    2026,
                    1,
                    16,
                    2,
                    tzinfo=UTC,
                ),
            ],
            "prediction": [
                101.5,
                102.5,
            ],
        }
    )

    generated = SimpleNamespace(
        records=forecast_records,
        forecast_origin=FORECAST_ORIGIN,
        generated_at=GENERATED_AT,
    )

    forecast_calls: list[
        tuple[Any, Any, pd.DataFrame, dict[str, Any]]
    ] = []

    def fake_generate_forecast(
        model: Any,
        model_metadata: Any,
        data: pd.DataFrame,
        **kwargs: Any,
    ) -> Any:
        forecast_calls.append(
            (
                model,
                model_metadata,
                data.copy(deep=True),
                kwargs,
            )
        )
        return generated

    monkeypatch.setattr(
        pipeline_module,
        "generate_forecast",
        fake_generate_forecast,
    )
    monkeypatch.setattr(
        pipeline_module,
        "utc_now",
        lambda: GENERATED_AT,
    )

    pipeline = ModelingPipeline(
        storage=storage,
        paths=paths,
    )

    result = pipeline.forecast(definition)

    assert result.status == "success"
    assert result.reason == "Forecast generated"
    assert result.records_read == 4
    assert result.records_written == 2
    assert result.model_version == "model-v1"
    assert result.forecast_origin == FORECAST_ORIGIN
    assert result.generated_at == GENERATED_AT

    assert len(forecast_calls) == 1

    (
        received_model,
        received_metadata,
        received_data,
        received_settings,
    ) = forecast_calls[0]

    assert received_model is fake_model
    assert received_metadata is metadata
    assert len(received_data) == 4
    assert received_settings == {
        "timestamp_column": "observed_at",
        "generated_at": GENERATED_AT,
        "forecast_steps": 2,
        "frequency": "1h",
    }

    stored = storage.read_dataset(
        definition.forecast_output
    )

    assert len(stored) == 2
    assert stored["forecast_id"].tolist() == [
        "forecast-1",
        "forecast-2",
    ]


def test_forecast_returns_failure_when_model_is_missing(
    storage,
    paths,
):
    definition = make_model_definition()

    def raise_missing_model(
        path: str,
    ) -> None:
        raise FileNotFoundError(
            "Saved model was not found"
        )

    storage.read_model = raise_missing_model

    pipeline = ModelingPipeline(
        storage=storage,
        paths=paths,
    )

    result = pipeline.forecast(definition)

    assert result.status == "failure"
    assert result.reason == (
        "Forecasting raised an exception"
    )
    assert result.error == (
        "Saved model was not found"
    )
    assert result.records_read == 0
    assert result.records_written == 0