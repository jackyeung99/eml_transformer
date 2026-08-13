from __future__ import annotations

import typer

from eml_transformer.cli.stages import (
    run_datasets,
    run_embeddings,
    run_features,
    run_ingestion,
    run_scraping,
    run_standardization,
)
from eml_transformer.runtime import build_runtime


def run(
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
    include_embeddings: bool = typer.Option(
        True,
        "--embeddings/--no-embeddings",
    ),
) -> None:
    from eml_transformer.cli.main import print_result_table

    runtime = build_runtime(config)

    stages = [
        (
            "Ingestion Results",
            lambda: run_ingestion(runtime, source),
        ),
        (
            "Standardization Results",
            lambda: run_standardization(runtime, source),
        ),
        (
            "Scraping Results",
            lambda: run_scraping(runtime, source),
        ),
    ]

    if include_embeddings:
        stages.append(
            (
                "Embedding Results",
                lambda: run_embeddings(runtime, source),
            )
        )

    stages.extend(
        [
            (
                "Feature Results",
                lambda: run_features(runtime),
            ),
            (
                "Dataset Results",
                lambda: run_datasets(runtime),
            ),
        ]
    )

    for title, execute in stages:
        results = execute()
        print_result_table(title, results)