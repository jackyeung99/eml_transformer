
from __future__ import annotations

import logging

from eml_transformer.config.definitions import (
    ModelDefinition,
    ExperimentDefinition
)
from eml_transformer.modeling.results import (
    ForecastResult,
    TrainingResult,
    ExperimentResult
)
from eml_transformer.modeling.registry import create_model
from eml_transformer.modeling.training import (
    train_model, 
    should_train,
    TrainingDecision
)
from eml_transformer.modeling.forecasting import generate_forecast

from eml_transformer.modeling.artifacts import (
    ModelMetadata,
    build_model_version
) 

from eml_transformer.utils.dates import utc_now
from eml_transformer.storage.paths import StoragePaths
from eml_transformer.storage.base import Storage

logger = logging.getLogger(__name__)


class ModelingPipeline:
    def __init__(
        self,
        storage: Storage,
        paths: StoragePaths,
    ) -> None:
        self.storage = storage
        self.paths = paths

    def train(
        self,
        definition: ModelDefinition,
        *,
        force: bool = False,
    ) -> TrainingResult:
        records_read = 0
        model_path = self.paths.model(definition.model_output)

        try:
            existing_metadata = self.storage.read_model_metadata(
                model_path
            )

            if force:
                decision = TrainingDecision(
                    should_train=True,
                    reason="Training was forced",
                )
            else:
                decision = should_train(
                    metadata=existing_metadata,
                    retrain_after_hours=(
                        definition.retrain_after_hours
                    ),
                )

            if not decision.should_train:
                assert existing_metadata is not None

                return TrainingResult(
                    status="skipped",
                    name=definition.name,
                    reason=decision.reason,
                    model_ref=definition.model_output,
                    trained_at=existing_metadata.trained_at,
                )

            data = self.storage.read_dataset(
                definition.training_input
            )
            records_read = len(data)

            if data.empty:
                return TrainingResult(
                    status="skipped",
                    name=definition.name,
                    reason="Training dataset is empty",
                    records_read=0,
                    model_ref=definition.model_output,
                )

            model = create_model(
                definition.model_type,
                definition.hyper_parameters,
            )

            trained = train_model(
                model,
                data,
                features=definition.features,
                target=definition.target,
                timestamp_column=(
                    definition.training_settings.get(
                        "timestamp_column",
                        "observed_at",
                    )
                ),
                lookback_days=(
                    definition.training_settings.get(
                        "lookback_days",
                        730,
                    )
                ),
                validation_days=(
                    definition.training_settings.get(
                        "validation_days",
                        14,
                    )
                ),
            )

    
            trained_at = utc_now()
            model_version = build_model_version(trained_at)

            metadata = ModelMetadata(
                name=definition.name,
                model_type=definition.model_type,
                model_version=model_version,
                trained_at=trained_at,
                features=trained.features,
                target=trained.target,
                records_used=trained.records_used,
                records_trained=trained.records_trained,
                records_validated=trained.records_validated,
                hyper_parameters=dict(
                    definition.hyper_parameters
                ),
                training_settings=dict(
                    definition.training_settings
                ),
                metrics=dict(trained.metrics),
                diagnostics=dict(trained.diagnostics),
                training_start=trained.training_start,
                training_end=trained.training_end,
                validation_start=trained.validation_start,
                validation_end=trained.validation_end,
            )

            self.storage.write_model(
                model_path,
                trained.model,
                metadata,
            )

            return TrainingResult(
                status="success",
                name=definition.name,
                reason=decision.reason,
                records_read=records_read,
                records_trained=trained.records_used,
                records_validated=trained.records_validated,
                metrics=trained.metrics,
                model_ref=definition.model_output,
                trained_at=trained_at,
            )

        except Exception as exc:
            logger.exception(
                "Training failed for %s",
                definition.name,
            )

            return TrainingResult(
                status="failure",
                name=definition.name,
                reason="Training raised an exception",
                error=str(exc),
                records_read=records_read,
                model_ref=definition.model_output,
            )
        
    def forecast(
        self,
        definition: ModelDefinition,
    ) -> ForecastResult:
        records_read = 0
        records_written = 0

        model_path = self.paths.model(
            definition.model_output
        )

        try:
            model, metadata = self.storage.read_model(
                model_path
            )

            forecast_data = self.storage.read_dataset(
                definition.forecast_input
            )
            records_read = len(forecast_data)

            if forecast_data.empty:
                return ForecastResult(
                    status="skipped",
                    name=definition.name,
                    reason="Forecast input is empty",
                    records_read=0,
                    records_written=0,
                    model_ref=definition.model_output,
                    forecast_ref=definition.forecast_output,
                )


            forecast_settings = (
                definition.forecast_settings
            )

  
            generated = generate_forecast(
                model,
                metadata,
                forecast_data,
                timestamp_column=forecast_settings.get(
                    "timestamp_column",
                    "observed_at",
                ),
                generated_at=utc_now(),
                forecast_steps=forecast_settings.get(
                    "forecast_steps",
                    1,
                ),
                frequency=forecast_settings.get(
                    "frequency",
                    "1h",
                ),
            )

            records_written = self.storage.write_forecasts(
                definition.forecast_output,
                generated.records,
            )

            return ForecastResult(
                status="success",
                name=definition.name,
                reason="Forecast generated",
                records_read=records_read,
                records_written=records_written,
                model_ref=definition.model_output,
                forecast_ref=definition.forecast_output,
                model_version=metadata.model_version,
                forecast_origin=generated.forecast_origin,
                generated_at=generated.generated_at,
            )

        except Exception as exc:
            logger.exception(
                "Forecasting failed for %s",
                definition.name,
            )

            return ForecastResult(
                status="failure",
                name=definition.name,
                reason="Forecasting raised an exception",
                error=str(exc),
                records_read=records_read,
                records_written=records_written,
                model_ref=definition.model_output,
                forecast_ref=definition.forecast_output,
            )


        


    def experiment(
        self,
        definition: ExperimentDefinition,
    ) -> ExperimentResult:
        ...