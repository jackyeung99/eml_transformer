from __future__ import annotations

from datetime import datetime
from typing import Any

import typer

from eml_transformer.dataset.pipeline import DatasetOrchestrator
from eml_transformer.features.pipeline import FeatureOrchestrator
from eml_transformer.ingestion.historical_orchestrator import (
    BackfillPipeline,
)
from eml_transformer.ingestion.orchestrator import IngestionPipeline
from eml_transformer.modeling.pipeline import ModelingPipeline
from eml_transformer.runtime import Runtime, build_runtime
from eml_transformer.scraping.pipeline import ScrapingPipeline
from eml_transformer.standardization.pipeline import (
    StandardizationPipeline,
)
from eml_transformer.utils.dates import parse_utc_datetime


DEFAULT_CONFIG = "configs/dev.yaml"


# Pipeline runners

def run_ingestion(
    runtime: Runtime,
    source: str = "all",
) -> list[Any]:
    pipeline = IngestionPipeline(
        storage=runtime.storage,
        paths=runtime.paths,
    )

    return [
        pipeline.run_source(
            source_name=definition.name,
            source_config=definition.settings,
        )
        for definition in runtime.sources_for_stage(
            "ingest",
            requested=source,
        )
    ]


def run_standardization(
    runtime: Runtime,
    source: str = "all",
) -> list[Any]:
    pipeline = StandardizationPipeline(
        storage=runtime.storage,
        paths=runtime.paths,
    )

    return [
        pipeline.run_source(
            source_name=definition.name,
            source_config=definition.settings,
        )
        for definition in runtime.sources_for_stage(
            "standardize",
            requested=source,
        )
    ]


def run_scraping(
    runtime: Runtime,
    source: str = "all",
) -> list[Any]:
    pipeline = ScrapingPipeline(
        storage=runtime.storage,
        paths=runtime.paths,
    )

    return [
        pipeline.run_source(
            source_name=definition.name,
            source_config=definition.settings,
        )
        for definition in runtime.sources_for_stage(
            "scrape",
            requested=source,
        )
    ]


def run_embeddings(
    runtime: Runtime,
    source: str = "all",
    model_name: str | None = None,
) -> list[Any]:
    # Lazy import because sentence-transformers is optional.
    from eml_transformer.embeddings.orchestrator import (
        EmbeddingPipeline,
    )

    pipeline = EmbeddingPipeline(
        storage=runtime.storage,
        paths=runtime.paths,
    )

    results: list[Any] = []

    for definition in runtime.sources_for_stage(
        "embed",
        requested=source,
    ):
        embedding_config = runtime.effective_embedding_config(
            definition,
            model_name=model_name,
        )

        results.append(
            pipeline.run_source(
                source_name=definition.name,
                embedding_config=embedding_config,
            )
        )

    return results


def run_features(
    runtime: Runtime,
    feature: str = "all",
) -> list[Any]:
    pipeline = FeatureOrchestrator(
        storage=runtime.storage,
        paths=runtime.paths,
    )

    return [
        pipeline.build_feature_set(definition)
        for definition in runtime.features(feature)
    ]


def run_datasets(
    runtime: Runtime,
    dataset: str = "all",
) -> list[Any]:
    pipeline = DatasetOrchestrator(
        storage=runtime.storage,
        paths=runtime.paths,
    )

    return [
        pipeline.build_dataset(definition)
        for definition in runtime.datasets(dataset)
    ]


def run_training(
    runtime: Runtime,
    models: tuple[str, ...] = (),
    *,
    force: bool = False,
) -> list[Any]:
    pipeline = ModelingPipeline(
        storage=runtime.storage,
        paths=runtime.paths,
    )

    return [
        pipeline.train(definition, force=force)
        for definition in runtime.models(models)
    ]


def run_forecasting(
    runtime: Runtime,
    models: tuple[str, ...] = (),
) -> list[Any]:
    pipeline = ModelingPipeline(
        storage=runtime.storage,
        paths=runtime.paths,
    )

    return [
        pipeline.forecast(definition)
        for definition in runtime.models(models)
    ]


def run_backfill(
    runtime: Runtime,
    source: str,
    from_date: datetime,
    to_date: datetime,
    window_days: int,
    init_checkpoint: bool,
) -> list[Any]:
    ingestion_pipeline = IngestionPipeline(
        storage=runtime.storage,
        paths=runtime.paths,
    )
    pipeline = BackfillPipeline(
        ingestion_pipeline=ingestion_pipeline,
    )

    return [
        pipeline.run_source(
            source_name=definition.name,
            source_config=definition.settings,
            from_date=from_date,
            to_date=to_date,
            window_days=window_days,
            seed_checkpoint=init_checkpoint,
        )
        for definition in runtime.sources_for_stage(
            "backfill",
            requested=source,
        )
    ]


# Command helpers

def print_results(
    title: str,
    results: list[Any],
    *,
    exit_on_failure: bool = True,
) -> None:
    from eml_transformer.cli.main import print_result_table

    print_result_table(title, results)

    if exit_on_failure and any(
        getattr(result, "status", None) == "failure"
        for result in results
    ):
        raise typer.Exit(1)


# Typer commands

def ingest(
    source: str = typer.Option("all", "--source", "-s"),
    config: str = typer.Option(
        DEFAULT_CONFIG,
        "--config",
        "-c",
    ),
) -> None:
    results = run_ingestion(
        build_runtime(config),
        source=source,
    )
    print_results("Ingestion Results", results)


def standardize(
    source: str = typer.Option("all", "--source", "-s"),
    config: str = typer.Option(
        DEFAULT_CONFIG,
        "--config",
        "-c",
    ),
) -> None:
    results = run_standardization(
        build_runtime(config),
        source=source,
    )
    print_results("Standardization Results", results)


def scrape(
    source: str = typer.Option("all", "--source", "-s"),
    config: str = typer.Option(
        DEFAULT_CONFIG,
        "--config",
        "-c",
    ),
) -> None:
    results = run_scraping(
        build_runtime(config),
        source=source,
    )
    print_results("Scraping Results", results)


def embed(
    source: str = typer.Option("all", "--source", "-s"),
    model_name: str | None = typer.Option(
        None,
        "--model",
        "-m",
    ),
    config: str = typer.Option(
        DEFAULT_CONFIG,
        "--config",
        "-c",
    ),
) -> None:
    results = run_embeddings(
        build_runtime(config),
        source=source,
        model_name=model_name,
    )
    print_results("Embedding Results", results)


def build_features(
    feature: str = typer.Option(
        "all",
        "--feature",
        "-f",
    ),
    config: str = typer.Option(
        DEFAULT_CONFIG,
        "--config",
        "-c",
    ),
) -> None:
    results = run_features(
        build_runtime(config),
        feature=feature,
    )
    print_results("Feature Results", results)


def build_dataset(
    dataset: str = typer.Option(
        "all",
        "--dataset",
        "-d",
    ),
    config: str = typer.Option(
        DEFAULT_CONFIG,
        "--config",
        "-c",
    ),
) -> None:
    results = run_datasets(
        build_runtime(config),
        dataset=dataset,
    )
    print_results("Dataset Results", results)


def train_models(
    names: list[str] | None = typer.Argument(
        None,
        help="Models to train. Defaults to all enabled models.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Train even when the existing model is current.",
    ),
    config: str = typer.Option(
        DEFAULT_CONFIG,
        "--config",
        "-c",
    ),
) -> None:
    results = run_training(
        build_runtime(config),
        models=tuple(names or ()),
        force=force,
    )
    print_results("Training Results", results)


def forecast(
    names: list[str] | None = typer.Argument(
        None,
        help="Models to forecast. Defaults to all enabled models.",
    ),
    config: str = typer.Option(
        DEFAULT_CONFIG,
        "--config",
        "-c",
    ),
) -> None:
    results = run_forecasting(
        build_runtime(config),
        models=tuple(names or ()),
    )
    print_results("Forecasting Results", results)


def backfill(
    source: str = typer.Option(..., "--source", "-s"),
    from_date: str = typer.Option(..., "--from-date"),
    to_date: str = typer.Option(..., "--to-date"),
    window_days: int = typer.Option(
        30,
        "--window-days",
        min=1,
    ),
    init_checkpoint: bool = typer.Option(
        False,
        "--init-checkpoint",
    ),
    config: str = typer.Option(
        DEFAULT_CONFIG,
        "--config",
        "-c",
    ),
) -> None:
    start = parse_utc_datetime(from_date)
    end = parse_utc_datetime(to_date)

    if start >= end:
        raise typer.BadParameter(
            "--from-date must be earlier than --to-date"
        )

    results = run_backfill(
        runtime=build_runtime(config),
        source=source,
        from_date=start,
        to_date=end,
        window_days=window_days,
        init_checkpoint=init_checkpoint,
    )
    print_results("Backfill Results", results)