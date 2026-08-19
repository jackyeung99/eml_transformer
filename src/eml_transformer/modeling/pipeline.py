from __future__ import annotations

from time import perf_counter

from eml_transformer.config.definitions import (
    ExperimentDefinition,
    ModelDefinition,
)
from eml_transformer.logging import get_logger
from eml_transformer.modeling.artifacts import (
    ModelMetadata,
    build_model_version,
)
from eml_transformer.modeling.forecasting import (
    generate_forecast,
)
from eml_transformer.modeling.registry import create_model
from eml_transformer.modeling.results import (
    ExperimentResult,
    ForecastResult,
    TrainingResult,
)
from eml_transformer.modeling.training import (
    TrainingDecision,
    should_train,
    train_model,
)
from eml_transformer.storage.base import Storage
from eml_transformer.storage.paths import StoragePaths
from eml_transformer.utils.dates import utc_now

logger = get_logger(__name__)


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
        started_at = perf_counter()
        records_read = 0

        model_path = self.paths.model(
            definition.model_output
        )

        logger.info(
            "Starting model training "
            "| model=%s "
            "| type=%s "
            "| input=%s "
            "| output=%s "
            "| force=%s",
            definition.name,
            definition.model_type,
            definition.training_input,
            definition.model_output,
            force,
        )

        try:
            step_started_at = perf_counter()

            existing_metadata = (
                self.storage.read_model_metadata(
                    definition.model_output
                )
            )


            logger.info(
                "Loaded model metadata "
                "| model=%s "
                "| exists=%s "
                "| elapsed=%.2fs",
                definition.name,
                existing_metadata is not None,
                perf_counter() - step_started_at,
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

            logger.info(
                "Evaluated training decision "
                "| model=%s "
                "| should_train=%s "
                "| reason=%s",
                definition.name,
                decision.should_train,
                decision.reason,
            )

            if not decision.should_train:
                assert existing_metadata is not None

                logger.info(
                    "Skipping model training "
                    "| model=%s "
                    "| reason=%s "
                    "| elapsed=%.2fs",
                    definition.name,
                    decision.reason,
                    perf_counter() - started_at,
                )

                return TrainingResult(
                    status="skipped",
                    name=definition.name,
                    reason=decision.reason,
                    model_ref=definition.model_output,
                    trained_at=existing_metadata.trained_at,
                )

            step_started_at = perf_counter()

            logger.info(
                "Reading training dataset "
                "| model=%s "
                "| input=%s",
                definition.name,
                definition.training_input,
            )

            data = self.storage.read_dataset(
                definition.training_input
            )
            records_read = len(data)

            logger.info(
                "Loaded training dataset "
                "| model=%s "
                "| records=%d "
                "| columns=%d "
                "| elapsed=%.2fs",
                definition.name,
                records_read,
                len(data.columns),
                perf_counter() - step_started_at,
            )

            if data.empty:
                logger.warning(
                    "Skipping model training because "
                    "the dataset is empty "
                    "| model=%s "
                    "| input=%s "
                    "| elapsed=%.2fs",
                    definition.name,
                    definition.training_input,
                    perf_counter() - started_at,
                )

                return TrainingResult(
                    status="skipped",
                    name=definition.name,
                    reason="Training dataset is empty",
                    records_read=0,
                    model_ref=definition.model_output,
                )

            step_started_at = perf_counter()

            logger.info(
                "Creating forecast model "
                "| model=%s "
                "| type=%s",
                definition.name,
                definition.model_type,
            )

            model = create_model(
                definition.model_type,
                definition.hyper_parameters,
            )

            logger.info(
                "Created forecast model "
                "| model=%s "
                "| elapsed=%.2fs",
                definition.name,
                perf_counter() - step_started_at,
            )

            step_started_at = perf_counter()

            logger.info(
                "Fitting forecast model "
                "| model=%s "
                "| records=%d "
                "| features=%d "
                "| target=%s",
                definition.name,
                records_read,
                len(definition.features),
                definition.target,
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

            logger.info(
                "Finished fitting forecast model "
                "| model=%s "
                "| trained=%d "
                "| validated=%d "
                "| elapsed=%.2fs",
                definition.name,
                trained.records_trained,
                trained.records_validated,
                perf_counter() - step_started_at,
            )

            trained_at = utc_now()
            model_version = build_model_version(
                trained_at
            )

            metadata = ModelMetadata(
                name=definition.name,
                model_type=definition.model_type,
                model_version=model_version,
                trained_at=trained_at,
                features=trained.features,
                target=trained.target,
                records_used=trained.records_used,
                records_trained=trained.records_trained,
                records_validated=(
                    trained.records_validated
                ),
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

            step_started_at = perf_counter()

            logger.info(
                "Writing model artifacts "
                "| model=%s "
                "| version=%s "
                "| path=%s",
                definition.name,
                model_version,
                model_path,
            )

            self.storage.write_model(
                definition.model_output,
                trained.model,
                metadata,
            )

            logger.info(
                "Wrote model artifacts "
                "| model=%s "
                "| version=%s "
                "| elapsed=%.2fs",
                definition.name,
                model_version,
                perf_counter() - step_started_at,
            )

            logger.info(
                "Completed model training "
                "| model=%s "
                "| version=%s "
                "| records_read=%d "
                "| records_trained=%d "
                "| records_validated=%d "
                "| total_elapsed=%.2fs",
                definition.name,
                model_version,
                records_read,
                trained.records_trained,
                trained.records_validated,
                perf_counter() - started_at,
            )

            return TrainingResult(
                status="success",
                name=definition.name,
                reason=decision.reason,
                records_read=records_read,
                records_trained=trained.records_trained,
                records_validated=(
                    trained.records_validated
                ),
                metrics=trained.metrics,
                model_ref=definition.model_output,
                trained_at=trained_at,
            )

        except Exception as exc:
            logger.exception(
                "Model training failed "
                "| model=%s "
                "| records_read=%d "
                "| elapsed=%.2fs",
                definition.name,
                records_read,
                perf_counter() - started_at,
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
        started_at = perf_counter()
        records_read = 0
        records_written = 0

        model_path = self.paths.model(
            definition.model_output
        )

        logger.info(
            "Starting forecast generation "
            "| model=%s "
            "| model_ref=%s "
            "| input=%s "
            "| output=%s",
            definition.name,
            definition.model_output,
            definition.forecast_input,
            definition.forecast_output,
        )

        try:
            step_started_at = perf_counter()

            logger.info(
                "Reading model artifacts "
                "| model=%s "
                "| path=%s",
                definition.name,
                model_path,
            )

            model, metadata = self.storage.read_model(
                definition.model_output
            )

            logger.info(
                "Loaded model artifacts "
                "| model=%s "
                "| version=%s "
                "| elapsed=%.2fs",
                definition.name,
                metadata.model_version,
                perf_counter() - step_started_at,
            )

            step_started_at = perf_counter()

            logger.info(
                "Reading forecast input "
                "| model=%s "
                "| input=%s",
                definition.name,
                definition.forecast_input,
            )

            forecast_data = self.storage.read_dataset(
                definition.forecast_input
            )
            records_read = len(forecast_data)

            logger.info(
                "Loaded forecast input "
                "| model=%s "
                "| records=%d "
                "| columns=%d "
                "| elapsed=%.2fs",
                definition.name,
                records_read,
                len(forecast_data.columns),
                perf_counter() - step_started_at,
            )

            if forecast_data.empty:
                logger.warning(
                    "Skipping forecast because input "
                    "dataset is empty "
                    "| model=%s "
                    "| input=%s "
                    "| elapsed=%.2fs",
                    definition.name,
                    definition.forecast_input,
                    perf_counter() - started_at,
                )

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
                definition.forecast_settings or {}
            )

            step_started_at = perf_counter()

            logger.info(
                "Generating forecast "
                "| model=%s "
                "| version=%s "
                "| steps=%s "
                "| frequency=%s",
                definition.name,
                metadata.model_version,
                forecast_settings.get(
                    "forecast_steps",
                    1,
                ),
                forecast_settings.get(
                    "frequency",
                    "1h",
                ),
            )

            generated = generate_forecast(
                model,
                metadata,
                forecast_data,
                timestamp_column=(
                    forecast_settings.get(
                        "timestamp_column",
                        "observed_at",
                    )
                ),
                generated_at=utc_now(),
                forecast_steps=(
                    forecast_settings.get(
                        "forecast_steps",
                        1,
                    )
                ),
                frequency=(
                    forecast_settings.get(
                        "frequency",
                        "1h",
                    )
                ),
            )

            logger.info(
                "Generated forecast "
                "| model=%s "
                "| records=%d "
                "| origin=%s "
                "| elapsed=%.2fs",
                definition.name,
                len(generated.records),
                generated.forecast_origin,
                perf_counter() - step_started_at,
            )

            step_started_at = perf_counter()

            logger.info(
                "Writing forecasts "
                "| model=%s "
                "| output=%s "
                "| records=%d",
                definition.name,
                definition.forecast_output,
                len(generated.records),
            )

            records_written = (
                self.storage.write_forecasts(
                    definition.forecast_output,
                    generated.records,
                )
            )

            logger.info(
                "Wrote forecasts "
                "| model=%s "
                "| records=%d "
                "| elapsed=%.2fs",
                definition.name,
                records_written,
                perf_counter() - step_started_at,
            )

            logger.info(
                "Completed forecast generation "
                "| model=%s "
                "| version=%s "
                "| records_read=%d "
                "| records_written=%d "
                "| total_elapsed=%.2fs",
                definition.name,
                metadata.model_version,
                records_read,
                records_written,
                perf_counter() - started_at,
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
                "Forecast generation failed "
                "| model=%s "
                "| records_read=%d "
                "| records_written=%d "
                "| elapsed=%.2fs",
                definition.name,
                records_read,
                records_written,
                perf_counter() - started_at,
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
        logger.info(
            "Starting experiment "
            "| experiment=%s",
            definition.name,
        )

        raise NotImplementedError(
            "Experiment execution is not implemented"
        )