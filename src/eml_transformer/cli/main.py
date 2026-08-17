from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import typer
from dotenv import load_dotenv

from eml_transformer.logging import setup_logging
from eml_transformer.cli import inspect, stages, workflows


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



app = typer.Typer(
    help="EML Transformer data and modeling pipelines.",
)

# Individual pipeline stages remain top-level.
app.command("ingest")(stages.ingest)
app.command("backfill")(stages.backfill)
app.command("standardize")(stages.standardize)
app.command("scrape")(stages.scrape)
app.command("embed")(stages.embed)
app.command("features")(stages.build_features)
app.command("dataset")(stages.build_dataset)
app.command("train")(stages.train_models)
app.command("forecast")(stages.forecast)

# Register command groups.
app.add_typer(
    workflows.workflow_app,
    name="workflow",
)

app.add_typer(
    inspect.inspect_app,
    name="show",
)

if __name__ == "__main__":
    app()