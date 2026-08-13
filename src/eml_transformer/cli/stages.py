from __future__ import annotations

from datetime import datetime
from typing import Any

import typer

from eml_transformer.dataset.pipeline import DatasetOrchestrator
from eml_transformer.features.pipeline import FeatureOrchestrator
from eml_transformer.ingestion.historical_orchestrator import (
    BackfillPipeline,
)
from eml_transformer.ingestion.orchestrator import (
    IngestionPipeline,
)
from eml_transformer.runtime import Runtime, build_runtime
from eml_transformer.scraping.pipeline import ScrapingPipeline
from eml_transformer.standardization.pipeline import (
    StandardizationPipeline,
)
from eml_transformer.utils.dates import parse_utc_datetime


def run_ingestion(
    runtime: Runtime,
    source: str = "all",
) -> list[Any]:
    pipeline = IngestionPipeline(
        storage=runtime.storage,
        paths=runtime.paths,
    )

    definitions = runtime.sources_for_stage(
        "ingest",
        requested=source,
    )

    return [
        pipeline.run_source(
            source_name=definition.name,
            source_config=definition.settings,
        )
        for definition in definitions
    ]


def run_standardization(
    runtime: Runtime,
    source: str = "all",
) -> list[Any]:
    pipeline = StandardizationPipeline(
        storage=runtime.storage,
        paths=runtime.paths,
    )

    definitions = runtime.sources_for_stage(
        "standardize",
        requested=source,
    )

    return [
        pipeline.run_source(
            source_name=definition.name,
            source_config=definition.settings,
        )
        for definition in definitions
    ]


def run_scraping(
    runtime: Runtime,
    source: str = "all",
) -> list[Any]:
    pipeline = ScrapingPipeline(
        storage=runtime.storage,
        paths=runtime.paths,
    )

    definitions = runtime.sources_for_stage(
        "scrape",
        requested=source,
    )

    return [
        pipeline.run_source(
            source_name=definition.name,
            source_config=definition.settings,
        )
        for definition in definitions
    ]


def run_embeddings(
    runtime: Runtime,
    source: str = "all",
    model_name: str | None = None,
) -> list[Any]:
    # Keep this lazy if sentence-transformers is optional.
    from eml_transformer.embeddings.orchestrator import (
        EmbeddingPipeline,
    )

    pipeline = EmbeddingPipeline(
        storage=runtime.storage,
        paths=runtime.paths,
    )

    definitions = runtime.sources_for_stage(
        "embed",
        requested=source,
    )

    results = []

    for definition in definitions:
        embedding_config = (
            runtime.effective_embedding_config(
                definition,
                model_name=model_name,
            )
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

    definitions = runtime.sources_for_stage(
        "backfill",
        requested=source,
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
        for definition in definitions
    ]



# Typer Commands
def ingest(
    source: str = typer.Option("all", "--source", "-s"),
    config: str = typer.Option(
        "configs/dev.yaml",
        "--config",
        "-c",
    ),
) -> None:
    from eml_transformer.cli.main import print_result_table

    results = run_ingestion(
        build_runtime(config),
        source=source,
    )
    print_result_table("Ingestion Results", results)


def standardize(
    source: str = typer.Option("all", "--source", "-s"),
    config: str = typer.Option(
        "configs/dev.yaml",
        "--config",
        "-c",
    ),
) -> None:
    from eml_transformer.cli.main import print_result_table

    results = run_standardization(
        build_runtime(config),
        source=source,
    )
    print_result_table("Standardization Results", results)


def scrape(
    source: str = typer.Option("all", "--source", "-s"),
    config: str = typer.Option(
        "configs/dev.yaml",
        "--config",
        "-c",
    ),
) -> None:
    from eml_transformer.cli.main import print_result_table

    results = run_scraping(
        build_runtime(config),
        source=source,
    )
    print_result_table("Scraping Results", results)


def embed(
    source: str = typer.Option("all", "--source", "-s"),
    model_name: str | None = typer.Option(
        None,
        "--model",
        "-m",
    ),
    config: str = typer.Option(
        "configs/dev.yaml",
        "--config",
        "-c",
    ),
) -> None:
    from eml_transformer.cli.main import print_result_table

    results = run_embeddings(
        build_runtime(config),
        source=source,
        model_name=model_name,
    )
    print_result_table("Embedding Results", results)


def build_features(
    feature: str = typer.Option(
        "all",
        "--feature",
        "-f",
    ),
    config: str = typer.Option(
        "configs/dev.yaml",
        "--config",
        "-c",
    ),
) -> None:
    from eml_transformer.cli.main import print_result_table

    results = run_features(
        build_runtime(config),
        feature=feature,
    )
    print_result_table("Feature Results", results)


def build_dataset(
    dataset: str = typer.Option(
        "all",
        "--dataset",
        "-d",
    ),
    config: str = typer.Option(
        "configs/dev.yaml",
        "--config",
        "-c",
    ),
) -> None:
    from eml_transformer.cli.main import print_result_table

    results = run_datasets(
        build_runtime(config),
        dataset=dataset,
    )
    print_result_table("Dataset Results", results)


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
        "configs/dev.yaml",
        "--config",
        "-c",
    ),
) -> None:
    from eml_transformer.cli.main import print_result_table

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

    print_result_table("Backfill Results", results)