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
    stage: str | None = typer.Option(
        None,
        "--stage",
        "-s",
        help="Filter sources by stage.",
    ),
    config: str = typer.Option(
        "configs/dev.yaml",
        "--config",
        "-c",
    ),
) -> None:
    runtime = build_runtime(config)

    if stage is not None:
        definitions = runtime.sources_for_stage(
            stage=stage,
            requested="all",
        )

        typer.echo(f"Enabled sources for {stage!r}:")

        if not definitions:
            typer.echo("  None")
            return

        for definition in definitions:
            typer.echo(f"- {definition.name}")

        return

    typer.echo("Configured sources:")

    for definition in runtime.config.sources.values():
        status = "enabled" if definition.enabled else "disabled"
        stages = ", ".join(sorted(definition.stages)) or "none"

        typer.echo(
            f"- {definition.name} "
            f"({status}; stages: {stages})"
        )

@app.command()
def ingest(
    source: str = typer.Option("all", "--source", "-s"),
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

    sources = rt.sources_for_stage(
        "ingest",
        requested=source,
    )

    results = [
        pipeline.run_source(
            source_name=definition.name,
            source_config=definition.settings,
        )
        for definition in sources
    ]

    print_result_table("Ingestion Results", results)


@app.command()
def standardize(
    source: str = typer.Option("all", "--source", "-s"),
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

    sources = rt.sources_for_stage(
        "standardize",
        requested=source,
    )

    results = [
        pipeline.run_source(
            source_name=definition.name,
            source_config=definition.settings,
        )
        for definition in sources
    ]

    print_result_table("Standardization Results", results)

@app.command()
def scrape(
    source: str = typer.Option("all", "--source", "-s"),
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

    sources = rt.sources_for_stage(
        "scrape",
        requested=source,
    )

    results = [
        pipeline.run_source(
            source_name=definition.name,
            source_config=definition.settings,
        )
        for definition in sources
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
    from eml_transformer.embeddings.orchestrator import (
        EmbeddingPipeline,
    )

    rt = build_runtime(config)

    pipeline = EmbeddingPipeline(
        storage=rt.storage,
        paths=rt.paths,
    )

    definitions = rt.sources_for_stage(
        stage="embed",
        requested=source,
    )

    results = []


    for definition in definitions:
        # combine root level embedding with source specific 
        embedding_config = rt.effective_embedding_config(
            definition,
            model_name=model_name,
        )

        results.append(
            pipeline.run_source(
                source_name=definition.name,
                embedding_config=embedding_config,
            )
        )

    print_result_table(
        "Embedding Results",
        results,
    )

@app.command()
def test(
    config: str = typer.Option(
            "configs/dev.yaml",
            "--config",
            "-c",
        ),
):
    rt = build_runtime(config)
    print(rt.storage)
    print(rt.paths)


@app.command()
def backfill(
    source: str = typer.Option(..., "--source", "-s"),
    from_date: str = typer.Option(..., "--from-date"),
    to_date: str = typer.Option(..., "--to-date"),
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

    sources = rt.sources_for_stage(
        "backfill",
        requested=source,
    )

    results = [
        pipeline.run_source(
            source_name=definition.name,
            source_config=definition.settings,
            from_date=from_date_utc,
            to_date=to_date_utc,
            window_days=window_days,
            seed_checkpoint=init_checkpoint,
        )
        for definition in sources
    ]

    print_result_table("Backfill Results", results)



@app.command("features")
def build_features(
    feature: str = typer.Option("all", "--feature", "-f"),
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

    features = rt.features(feature)

    results = [
        orchestrator.build_feature_set(
            definition=definition,
        )
        for definition in features
    ]

    print_result_table("Feature Results", results)


if __name__ == "__main__":
    app()