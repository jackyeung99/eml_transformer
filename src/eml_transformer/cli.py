from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import typer
from dotenv import load_dotenv

from eml_transformer.sources.registry import available_sources
from eml_transformer.logging import setup_logging

from eml_transformer.ingestion.historical_orchestrator import BackfillPipeline
from eml_transformer.ingestion.orchestrator import IngestionPipeline
from eml_transformer.standardization.orchestrator import StandardizationPipeline
from eml_transformer.scraping.orchestrator import ScrapingPipeline
from eml_transformer.features.orchestrator import FeatureOrchestrator

from eml_transformer.runtime import build_runtime
from eml_transformer.utils.dates import parse_utc_datetime

load_dotenv()

app = typer.Typer()
logger = logging.getLogger(__name__)


def print_result_table(title: str, results: list[Any]) -> None:
    rows = [
        result.to_summary()
        for result in results
    ]

    if not rows:
        typer.echo(f"\n{title}: no results")
        return

    df = pd.DataFrame(rows)

    typer.echo("\n" + "=" * 100)
    typer.echo(title.upper())
    typer.echo("=" * 100)
    typer.echo(df.to_string(index=False, max_colwidth=40))
    typer.echo("=" * 100 + '\n')


def get_source_config(
    source: str,
    source_configs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if source not in source_configs:
        available = ", ".join(sorted(source_configs))
        raise typer.BadParameter(
            f"Unknown source: {source}. Available sources: {available}"
        )

    return source_configs[source]


@app.callback()
def main(
    log_level: str = typer.Option("INFO"),
):
    setup_logging(
        level=getattr(logging, log_level.upper()),
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
    source: str = typer.Option("all"),
    config: str = typer.Option("configs/dev.yaml"),
):
    rt = build_runtime(config)

    pipeline = IngestionPipeline(
        storage=rt.storage,
        paths=rt.paths,
    )

    if source.lower() == "all":
        results = pipeline.run_all(rt.source_configs)
    else:
        source_config = get_source_config(source, rt.source_configs)
        results = [pipeline.run_source(source, source_config)]

    print_result_table("Ingestion Results", results)


@app.command("standardize")
def standardize(
    source: str = typer.Option("all"),
    config: str = typer.Option("configs/dev.yaml"),
):
    rt = build_runtime(config)

    pipeline = StandardizationPipeline(
        storage=rt.storage,
        paths=rt.paths,
    )

    if source.lower() == "all":
        results = pipeline.run_all(rt.source_configs)
    else:
        source_config = get_source_config(source, rt.source_configs)
        results = [pipeline.run_source(source, source_config)]

    print_result_table("Standardization Results", results)

@app.command("scrape")
def scrape(
    source: str = typer.Option("all"),
    config: str = typer.Option("configs/dev.yaml"),
):
    rt = build_runtime(config)

    pipeline = ScrapingPipeline(
        storage=rt.storage,
        paths=rt.paths,
    )

    if source.lower() == "all":
        results = pipeline.run_all(rt.source_configs)
    else:
        source_config = get_source_config(source, rt.source_configs)
        results = [pipeline.run_source(source, source_config)]

    print_result_table("Scraping Results", results)

@app.command()
def embed(
    source: str = typer.Option("all"),
    model_name: str | None = typer.Option(None, "--model", "-m"),
    config: str = typer.Option("configs/dev.yaml"),
):
    from eml_transformer.embeddings.orchestrator import EmbeddingPipeline

    rt = build_runtime(config)

    embedding_config = dict(rt.embedding_config)

    if model_name is not None:
        embedding_config["model"] = model_name

    pipeline = EmbeddingPipeline(
        storage=rt.storage,
        paths=rt.paths,
    )

    if source.lower() == "all":
        results = pipeline.run_all(
            embedding_config=embedding_config,
            source_configs=rt.source_configs,
        )
    else:
        source_config = get_source_config(source, rt.source_configs)

        results = [
            pipeline.run_source(
                source=source,
                embedding_config=embedding_config,
                source_config=source_config
            )
        ]

    print_result_table("Embedding Results", results)


@app.command()
def ingest(
    source: str = typer.Option("all"),
    config: str = typer.Option("configs/dev.yaml"),
):
    rt = build_runtime(config)

    pipeline = FeatureOrchestrator(
        storage=rt.storage,
        paths=rt.paths,
    )

    if source.lower() == "all":
        results = pipeline.run_all(rt.source_configs)
    else:
        source_config = get_source_config(source, rt.source_configs)
        results = [pipeline.run_source(source, source_config)]

    print_result_table("Ingestion Results", results)


@app.command()
def backfill(
    source: str = typer.Option(..., "--source", "-s"),
    from_date: str = typer.Option(..., "--from-date"),
    to_date: str = typer.Option(..., "--to-date"),
    window_days: int = typer.Option(30, "--window-days"),
    config: str = typer.Option("configs/dev.yaml", "--config", "-c"),
    init_checkpoint: bool = typer.Option(False, "--init-checkpoint"),
):
    rt = build_runtime(config)

    # convert iso to utc timezone aware
    from_date_utc = parse_utc_datetime(from_date)
    to_date_utc = parse_utc_datetime(to_date)

    ingestion_pipeline = IngestionPipeline(
        storage=rt.storage,
        paths=rt.paths,
    )

    pipeline = BackfillPipeline(
        ingestion_pipeline=ingestion_pipeline,
    )

    if source.lower() == "all":
        results = pipeline.run_all(
            source_configs=rt.source_configs,
            from_date=from_date_utc,
            to_date=to_date_utc,
            window_days=window_days,
            seed_checkpoint=init_checkpoint,
        )
    else:
        source_config = get_source_config(source, rt.source_configs)
    
        results = [
            pipeline.run_source(
                source_name=source,
                source_config=source_config,
                from_date=from_date_utc,
                to_date=to_date_utc,
                window_days=window_days,
                seed_checkpoint=init_checkpoint,
            )
        ]

    print_result_table("Backfill Results", results)


if __name__ == "__main__":
    app()