from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import typer
from dotenv import load_dotenv

from eml_transformer.cli import stages, workflows
from eml_transformer.logging import setup_logging
from eml_transformer.runtime import build_runtime

load_dotenv()

app = typer.Typer(
    help="EML Transformer data and modeling pipelines.",
)


def print_result_table(
    title: str,
    results: list[Any],
) -> None:
    rows = [result.to_summary() for result in results]

    if not rows:
        typer.echo(f"\n{title}: no results")
        return

    frame = pd.DataFrame(rows)

    typer.echo("\n" + "=" * 100)
    typer.echo(title.upper())
    typer.echo("=" * 100)
    typer.echo(frame.to_string(index=False, max_colwidth=40))
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
        status = (
            "enabled"
            if definition.enabled
            else "disabled"
        )
        configured_stages = (
            ", ".join(sorted(definition.stages))
            or "none"
        )

        typer.echo(
            f"- {definition.name} "
            f"({status}; stages: {configured_stages})"
        )


# Register stage commands.
app.command("ingest")(stages.ingest)
app.command("backfill")(stages.backfill)
app.command("standardize")(stages.standardize)
app.command("scrape")(stages.scrape)
app.command("embed")(stages.embed)
app.command("features")(stages.build_features)
app.command("dataset")(stages.build_dataset)
app.command("train")(stages.train_models)

# Register workflow commands.
app.command("run")(workflows.run)


if __name__ == "__main__":
    app()