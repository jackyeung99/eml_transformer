from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

import typer

from eml_transformer.runtime import build_runtime


"""Commands for inspecting configured pipeline resources."""


DEFAULT_CONFIG = "configs/dev.yaml"

inspect_app = typer.Typer(
    help="Inspect configured pipeline resources.",
)


def _status(enabled: bool) -> str:
    return "enabled" if enabled else "disabled"


def _format_values(values: Iterable[Any]) -> str:
    items = list(values)
    return ", ".join(map(str, items)) if items else "none"


def _print_field(label: str, value: Any) -> None:
    if value in (None, "", (), [], {}):
        value = "none"

    typer.echo(f"    {label}: {value}")


def _print_mapping(
    label: str,
    values: Mapping[str, Any],
) -> None:
    if not values:
        _print_field(label, "none")
        return

    typer.echo(f"    {label}:")

    for key, value in values.items():
        typer.echo(f"      {key}: {value}")


def _print_definitions(
    title: str,
    definitions: Iterable[Any],
    details: Callable[[Any], str] | None = None,
) -> list[Any]:
    items = list(definitions)

    typer.echo(f"{title}:")

    if not items:
        typer.echo("  None")
        return []

    for definition in items:
        description = ""

        if details is not None:
            value = details(definition)

            if value:
                description = f"; {value}"

        typer.echo(
            f"- {definition.name} "
            f"({_status(definition.enabled)}"
            f"{description})"
        )

    return items


@inspect_app.command("sources")
def sources(
    stage: str | None = typer.Option(
        None,
        "--stage",
        "-s",
        help="Filter enabled sources by stage.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show source settings.",
    ),
    config: str = typer.Option(
        DEFAULT_CONFIG,
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
        title = f"Enabled sources for {stage!r}"
    else:
        definitions = runtime.config.sources.values()
        title = "Configured sources"

    items = _print_definitions(
        title,
        definitions,
        details=lambda definition: (
            "stages: "
            + _format_values(sorted(definition.stages))
        ),
    )

    if verbose:
        for definition in items:
            typer.echo(f"\n  {definition.name}")
            _print_mapping(
                "settings",
                definition.settings,
            )


@inspect_app.command("features")
def features(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show feature inputs, outputs, and settings.",
    ),
    config: str = typer.Option(
        DEFAULT_CONFIG,
        "--config",
        "-c",
    ),
) -> None:
    runtime = build_runtime(config)

    items = _print_definitions(
        "Configured features",
        runtime.config.features.values(),
        details=lambda definition: (
            f"builder: {definition.builder}"
        ),
    )

    if verbose:
        for definition in items:
            typer.echo(f"\n  {definition.name}")
            _print_field(
                "inputs",
                _format_values(definition.inputs),
            )
            _print_field("output", definition.output)
            _print_mapping(
                "settings",
                definition.settings,
            )


@inspect_app.command("datasets")
def datasets(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show dataset inputs, outputs, and settings.",
    ),
    config: str = typer.Option(
        DEFAULT_CONFIG,
        "--config",
        "-c",
    ),
) -> None:
    runtime = build_runtime(config)

    items = _print_definitions(
        "Configured datasets",
        runtime.config.datasets.values(),
        details=lambda definition: (
            f"builder: {definition.builder}"
        ),
    )

    if verbose:
        for definition in items:
            typer.echo(f"\n  {definition.name}")
            _print_field(
                "inputs",
                _format_values(definition.inputs),
            )
            _print_field("output", definition.output)
            _print_mapping(
                "settings",
                definition.settings,
            )


@inspect_app.command("models")
def models(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show model features and configuration settings.",
    ),
    config: str = typer.Option(
        DEFAULT_CONFIG,
        "--config",
        "-c",
    ),
) -> None:
    runtime = build_runtime(config)
    definitions = list(runtime.config.modeling.values())

    typer.echo("Configured models:")

    if not definitions:
        typer.echo("  None")
        return

    for definition in definitions:
        typer.echo(
            f"- {definition.name} "
            f"({_status(definition.enabled)})"
        )
        _print_field("type", definition.model_type)
        _print_field("target", definition.target)
        _print_field(
            "training input",
            definition.training_input,
        )
        _print_field(
            "forecast output",
            definition.forecast_output,
        )

        if not verbose:
            continue

        _print_field(
            "forecast input",
            definition.forecast_input,
        )
        _print_field(
            "model output",
            definition.model_output,
        )
        _print_field(
            "features",
            _format_values(definition.features),
        )
        _print_field(
            "retrain after",
            f"{definition.retrain_after_hours} hours",
        )
        _print_mapping(
            "hyperparameters",
            definition.hyper_parameters,
        )
        _print_mapping(
            "training settings",
            definition.training_settings,
        )
        _print_mapping(
            "forecast settings",
            definition.forecast_settings,
        )