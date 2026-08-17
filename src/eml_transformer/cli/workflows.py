from __future__ import annotations

from typing import Any

import typer
from datetime import datetime

from eml_transformer.cli.stages import (
    run_datasets,
    run_embeddings,
    run_features,
    run_forecasting,
    run_ingestion,
    run_scraping,
    run_backfill,
    run_standardization,
    run_training,
)
from eml_transformer.runtime import Runtime, build_runtime
from eml_transformer.utils.dates import parse_utc_datetime
from eml_transformer.cli.shared import (
    DEFAULT_CONFIG,
    exit_on_failure,
    print_result_table,
)



workflow_app = typer.Typer(
    help="Run multi-stage pipeline workflows.",
)


def _stop_on_failure(
    stage: str,
    results: list[Any],
) -> None:
    failures = [
        result
        for result in results
        if getattr(result, "status", None) == "failure"
    ]

    if failures:
        raise RuntimeError(
            f"{stage} failed for {len(failures)} item(s)"
        )


def run_numeric_workflow(
    runtime: Runtime,
    *,
    source: str = "all",
    feature: str = "all",
    dataset: str = "all",
    models: tuple[str, ...] = (),
    force_train: bool = False,
) -> dict[str, list[Any]]:
    results: dict[str, list[Any]] = {}

    results["ingestion"] = run_ingestion(
        runtime,
        source=source,
    )
    _stop_on_failure("Ingestion", results["ingestion"])

    results["standardization"] = run_standardization(
        runtime,
        source=source,
    )
    _stop_on_failure(
        "Standardization",
        results["standardization"],
    )

    results["features"] = run_features(
        runtime,
        feature=feature,
    )
    _stop_on_failure("Features", results["features"])

    results["datasets"] = run_datasets(
        runtime,
        dataset=dataset,
    )
    _stop_on_failure("Datasets", results["datasets"])

    results["training"] = run_training(
        runtime,
        models=models,
        force=force_train,
    )
    _stop_on_failure("Training", results["training"])

    results["forecasting"] = run_forecasting(
        runtime,
        models=models,
    )
    _stop_on_failure("Forecasting", results["forecasting"])

    return results


def run_text_workflow(
    runtime: Runtime,
    *,
    source: str = "all",
    model_name: str | None = None,
) -> dict[str, list[Any]]:
    results: dict[str, list[Any]] = {}

    results["ingestion"] = run_ingestion(
        runtime,
        source=source,
    )
    _stop_on_failure("Ingestion", results["ingestion"])

    results["standardization"] = run_standardization(
        runtime,
        source=source,
    )
    _stop_on_failure(
        "Standardization",
        results["standardization"],
    )

    results["scraping"] = run_scraping(
        runtime,
        source=source,
    )
    _stop_on_failure("Scraping", results["scraping"])

    results["embeddings"] = run_embeddings(
        runtime,
        source=source,
        model_name=model_name,
    )
    _stop_on_failure("Embeddings", results["embeddings"])

    return results


def run_modeling_workflow(
    runtime: Runtime,
    *,
    feature: str = "all",
    dataset: str = "all",
    models: tuple[str, ...] = (),
    force_train: bool = False,
) -> dict[str, list[Any]]:
    """Rebuild modeling artifacts without ingesting new source data."""
    results: dict[str, list[Any]] = {}

    results["features"] = run_features(
        runtime,
        feature=feature,
    )
    _stop_on_failure("Features", results["features"])

    results["datasets"] = run_datasets(
        runtime,
        dataset=dataset,
    )
    _stop_on_failure("Datasets", results["datasets"])

    results["training"] = run_training(
        runtime,
        models=models,
        force=force_train,
    )
    _stop_on_failure("Training", results["training"])

    results["forecasting"] = run_forecasting(
        runtime,
        models=models,
    )
    _stop_on_failure("Forecasting", results["forecasting"])

    return results

def run_historical_workflow(
    runtime: Runtime,
    *,
    source: str,
    from_date: datetime,
    to_date: datetime,
    window_days: int = 30,
    init_checkpoint: bool = False,
    build_downstream: bool = False,
    feature: str = "all",
    dataset: str = "all",
) -> dict[str, list[Any]]:
    results: dict[str, list[Any]] = {}

    results["backfill"] = run_backfill(
        runtime=runtime,
        source=source,
        from_date=from_date,
        to_date=to_date,
        window_days=window_days,
        init_checkpoint=init_checkpoint,
    )
    _stop_on_failure("Backfill", results["backfill"])

    results["standardization"] = run_standardization(
        runtime,
        source=source,
    )
    _stop_on_failure(
        "Standardization",
        results["standardization"],
    )

    if build_downstream:
        results["features"] = run_features(
            runtime,
            feature=feature,
        )
        _stop_on_failure(
            "Features",
            results["features"],
        )

        results["datasets"] = run_datasets(
            runtime,
            dataset=dataset,
        )
        _stop_on_failure(
            "Datasets",
            results["datasets"],
        )

    return results

def _print_workflow_results(
    results: dict[str, list[Any]],
) -> None:


    for stage, stage_results in results.items():
        print_result_table(
            stage.replace("_", " ").title(),
            stage_results,
        )


def numeric(
    source: str = typer.Option("all", "--source", "-s"),
    feature: str = typer.Option("all", "--feature", "-f"),
    dataset: str = typer.Option("all", "--dataset", "-d"),
    models: list[str] | None = typer.Option(
        None,
        "--model",
        "-m",
    ),
    force_train: bool = typer.Option(
        False,
        "--force-train",
    ),
    config: str = typer.Option(
        "configs/dev.yaml",
        "--config",
        "-c",
    ),
) -> None:
    try:
        results = run_numeric_workflow(
            build_runtime(config),
            source=source,
            feature=feature,
            dataset=dataset,
            models=tuple(models or ()),
            force_train=force_train,
        )
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    _print_workflow_results(results)


def text(
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
    try:
        results = run_text_workflow(
            build_runtime(config),
            source=source,
            model_name=model_name,
        )
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    _print_workflow_results(results)


def modeling(
    feature: str = typer.Option("all", "--feature", "-f"),
    dataset: str = typer.Option("all", "--dataset", "-d"),
    models: list[str] | None = typer.Option(
        None,
        "--model",
        "-m",
    ),
    force_train: bool = typer.Option(
        False,
        "--force-train",
    ),
    config: str = typer.Option(
        "configs/dev.yaml",
        "--config",
        "-c",
    ),
) -> None:
    try:
        results = run_modeling_workflow(
            build_runtime(config),
            feature=feature,
            dataset=dataset,
            models=tuple(models or ()),
            force_train=force_train,
        )
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    _print_workflow_results(results)


@workflow_app.command("historical")
def historical(
    source: str = typer.Option(
        ...,
        "--source",
        "-s",
        help="Source to backfill.",
    ),
    from_date: str = typer.Option(
        ...,
        "--from-date",
        help="Inclusive backfill start date.",
    ),
    to_date: str = typer.Option(
        ...,
        "--to-date",
        help="Exclusive backfill end date.",
    ),
    window_days: int = typer.Option(
        30,
        "--window-days",
        min=1,
        help="Number of days processed per backfill window.",
    ),
    init_checkpoint: bool = typer.Option(
        False,
        "--init-checkpoint",
        help="Initialize the ingestion checkpoint after backfilling.",
    ),
    build_downstream: bool = typer.Option(
        False,
        "--build-downstream",
        help="Build configured features and datasets after standardization.",
    ),
    feature: str = typer.Option(
        "all",
        "--feature",
        "-f",
        help="Feature definition to build when downstream processing is enabled.",
    ),
    dataset: str = typer.Option(
        "all",
        "--dataset",
        "-d",
        help="Dataset definition to build when downstream processing is enabled.",
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

    try:
        results = run_historical_workflow(
            build_runtime(config),
            source=source,
            from_date=start,
            to_date=end,
            window_days=window_days,
            init_checkpoint=init_checkpoint,
            build_downstream=build_downstream,
            feature=feature,
            dataset=dataset,
        )
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    _print_workflow_results(results)