
from __future__ import annotations

import logging

from eml_transformer.config.definitions import (
    ForecastDefinition,
    TrainingDefinition,
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
    decide_training,
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
        definition: TrainingDefinition,
        *,
        force: bool = False,
    ) -> TrainingResult:
        records_read = 0
        model_path = self.paths.model(definition.output)

        try:
            existing_metadata = (
                self.storage.read_model_metadata(model_path)
            )

            decision = decide_training(
                trained_at=(
                    existing_metadata.trained_at
                    if existing_metadata is not None
                    else None
                ),
                retrain_after=definition.retrain_after,
                force=force,
            )

            if not decision.should_train:
                return TrainingResult(
                    status="skipped",
                    name=definition.name,
                    reason=decision.reason,
                    model_ref=definition.output,
                    trained_at=existing_metadata.trained_at,
                )

            data = self.storage.read_dataset(
                self.paths.dataset(definition.input)
            )
            records_read = len(data)

            if data.empty:
                return TrainingResult(
                    status="skipped",
                    name=definition.name,
                    reason="empty_training_dataset",
                    records_read=0,
                    model_ref=definition.output,
                )

            model = create_model(
                definition.model,
                definition.parameters,
            )

            trained = train_model(
                model,
                data,
                features=definition.features,
                target=definition.target,
            )

            trained_at = utc_now()

            metadata = ModelMetadata(
                name=definition.name,
                model_type=definition.model,
                trained_at=trained_at,
                features=trained.features,
                target=trained.target,
                records_trained=trained.records_trained,
                parameters=definition.parameters,
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
                records_trained=trained.records_trained,
                model_ref=definition.output,
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
                reason="training_failed",
                records_read=records_read,
                model_ref=definition.output,
                error=str(exc),
            )
    def forecast(
        self,
        definition: ForecastDefinition,
    ) -> ForecastResult:
        ...


    def experiment(
        self,
        definition: ExperimentDefinition,
    ) -> ExperimentResult:
        ...