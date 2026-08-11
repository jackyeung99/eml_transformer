from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import typer
from dotenv import load_dotenv

from eml_transformer.features.orchestrator import FeatureOrchestrator
from eml_transformer.ingestion.historical_orchestrator import BackfillPipeline
from eml_transformer.ingestion.orchestrator import IngestionPipeline
from eml_transformer.logging import setup_logging
from eml_transformer.runtime import build_runtime
from eml_transformer.scraping.orchestrator import ScrapingPipeline
from eml_transformer.standardization.orchestrator import (
    StandardizationPipeline,
)
from eml_transformer.utils.dates import parse_utc_datetime


load_dotenv()

app = typer.Typer()
logger = logging.getLogger(__name__)


def print_result_table(
    title: str,
    results: list[Any],
) -> None:
    rows = [result.to_summary() for result in results]

    if not rows:
        typer.echo(f"\n{title}: no results")
        return

    df = pd.DataFrame(rows)

    typer.echo("\n" + "=" * 100)
    typer.echo(title.upper())
    typer.echo("=" * 100)
    typer.echo(df.to_string(index=False, max_colwidth=40))
    typer.echo("=" * 100 + "\n")


def resolve_configs(
    requested: str,
    all_configs: dict[str, Any],
    enabled_configs: dict[str, Any],
    *,
    kind: str,
) -> dict[str, Any]:
    if requested.lower() == "all":
        return enabled_configs

    if requested not in all_configs:
        available = ", ".join(sorted(all_configs))
        raise typer.BadParameter(
            f"Unknown {kind}: {requested}. "
            f"Available {kind}s: {available}"
        )

    return {requested: all_configs[requested]}


@app.callback()
def main(
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
    ),
) -> None:
    level = getattr(logging, log_level.upper(), None)

    if not isinstance(level, int):
        raise typer.BadParameter(
            f"Invalid log level: {log_level}"
        )

    setup_logging(
        level=level,
        log_file=None,
        force=False,
    )


@app.command()
def sources(
    config: str = typer.Option("configs/dev.yaml"),
) -> None:
    runtime = build_runtime(config)

    typer.echo("Configured sources:")

    for source_name in runtime.source_names:
        enabled = source_name in runtime.enabled_source_names
        status = "enabled" if enabled else "disabled"

        typer.echo(f"- {source_name} ({status})")

@app.command()
def ingest(
    source: str = typer.Option(
        "all",
        "--source",
        "-s",
    ),
    config: str = typer.Option(
        "configs/dev.yaml",
        "--config",
        "-c",
    ),
) -> None:
    rt = build_runtime(config)

    pipeline = IngestionPipeline(
        storage=rt.storage,
        paths=rt.paths,
    )

    selected_sources = resolve_configs(
        requested=source,
        all_configs=rt.source_configs,
        enabled_configs=rt.enabled_source_configs,
        kind="source",
    )

    results = [
        pipeline.run_source(
            source_name=source_name,
            source_config=source_config,
        )
        for source_name, source_config in selected_sources.items()
    ]

    print_result_table("Ingestion Results", results)


@app.command()
def standardize(
    source: str = typer.Option(
        "all",
        "--source",
        "-s",
    ),
    config: str = typer.Option(
        "configs/dev.yaml",
        "--config",
        "-c",
    ),
) -> None:
    rt = build_runtime(config)

    pipeline = StandardizationPipeline(
        storage=rt.storage,
        paths=rt.paths,
    )

    selected_sources = resolve_configs(
        requested=source,
        all_configs=rt.source_configs,
        enabled_configs=rt.enabled_source_configs,
        kind="source",
    )

    results = [
        pipeline.run_source(
            source_name=source_name,
            source_config=source_config,
        )
        for source_name, source_config in selected_sources.items()
    ]

    print_result_table("Standardization Results", results)


@app.command()
def scrape(
    source: str = typer.Option(
        "all",
        "--source",
        "-s",
    ),
    config: str = typer.Option(
        "configs/dev.yaml",
        "--config",
        "-c",
    ),
) -> None:
    rt = build_runtime(config)

    pipeline = ScrapingPipeline(
        storage=rt.storage,
        paths=rt.paths,
    )

    selected_sources = resolve_configs(
        requested=source,
        all_configs=rt.source_configs,
        enabled_configs=rt.enabled_source_configs,
        kind="source",
    )

    results = [
        pipeline.run_source(
            source_name=source_name,
            source_config=source_config,
        )
        for source_name, source_config in selected_sources.items()
    ]

    print_result_table("Scraping Results", results)


@app.command()
def embed(
    source: str = typer.Option(
        "all",
        "--source",
        "-s",
    ),
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
    # Imported here so commands that do not use embeddings do not load
    # embedding dependencies.
    from eml_transformer.embeddings.orchestrator import (
        EmbeddingPipeline,
    )

    rt = build_runtime(config)

    embedding_config = dict(rt.embedding_config)

    if model_name is not None:
        embedding_config["model"] = model_name

    pipeline = EmbeddingPipeline(
        storage=rt.storage,
        paths=rt.paths,
    )

    selected_sources = resolve_configs(
        requested=source,
        all_configs=rt.source_configs,
        enabled_configs=rt.enabled_source_configs,
        kind="source",
    )

    results = [
        pipeline.run_source(
            source=source_name,
            source_config=source_config,
            embedding_config=embedding_config,
        )
        for source_name, source_config in selected_sources.items()
    ]

    print_result_table("Embedding Results", results)


@app.command()
def backfill(
    source: str = typer.Option(
        ...,
        "--source",
        "-s",
    ),
    from_date: str = typer.Option(
        ...,
        "--from-date",
    ),
    to_date: str = typer.Option(
        ...,
        "--to-date",
    ),
    window_days: int = typer.Option(
        30,
        "--window-days",
        min=1,
    ),
    config: str = typer.Option(
        "configs/dev.yaml",
        "--config",
        "-c",
    ),
    init_checkpoint: bool = typer.Option(
        False,
        "--init-checkpoint",
    ),
) -> None:
    rt = build_runtime(config)

    from_date_utc = parse_utc_datetime(from_date)
    to_date_utc = parse_utc_datetime(to_date)

    if from_date_utc >= to_date_utc:
        raise typer.BadParameter(
            "--from-date must be earlier than --to-date"
        )

    ingestion_pipeline = IngestionPipeline(
        storage=rt.storage,
        paths=rt.paths,
    )

    pipeline = BackfillPipeline(
        ingestion_pipeline=ingestion_pipeline,
    )

    selected_sources = resolve_configs(
        requested=source,
        all_configs=rt.source_configs,
        enabled_configs=rt.enabled_source_configs,
        kind="source",
    )

    results = [
        pipeline.run_source(
            source_name=source_name,
            source_config=source_config,
            from_date=from_date_utc,
            to_date=to_date_utc,
            window_days=window_days,
            seed_checkpoint=init_checkpoint,
        )
        for source_name, source_config in selected_sources.items()
    ]

    print_result_table("Backfill Results", results)


@app.command("features")
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
    rt = build_runtime(config)

    orchestrator = FeatureOrchestrator(
        storage=rt.storage,
        paths=rt.paths,
    )

    selected_features = resolve_configs(
        requested=feature,
        all_configs=rt.feature_configs,
        enabled_configs=rt.enabled_feature_configs,
        kind="feature",
    )

    results = [
        orchestrator.build_feature_set(
            feature_name=feature_name,
            feature_config=feature_config,
        )
        for feature_name, feature_config in selected_features.items()
    ]

    print_result_table("Feature Results", results)


if __name__ == "__main__":
    app()