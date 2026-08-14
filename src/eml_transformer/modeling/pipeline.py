
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

from eml_transformer.modeling.artifacts import ModelMetadata
from eml_transformer.utils.dates import utc_now
from eml_transformer.storage.paths import StoragePaths
from eml_transformer.storage.storage import Storage

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

            metadata = ModelMetadata(
                name=definition.name,
                model_type=definition.model_type,
                trained_at=trained_at,
                features=trained.features,
                target=trained.target,
                records_used=trained.records_used,
                records_trained=trained.records_trained,
                records_validated=trained.records_validated,
                hyper_parameters=dict(definition.hyper_parameters),
                training_settings=dict(definition.training_settings),
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
        ...


    def experiment(
        self,
        definition: ExperimentDefinition,
    ) -> ExperimentResult:
        ...