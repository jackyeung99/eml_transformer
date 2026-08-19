from __future__ import annotations

import logging
import typer
from dotenv import load_dotenv

from eml_transformer.logging import setup_logging
from eml_transformer.cli import inspect, stages, workflows


load_dotenv()

app = typer.Typer(
    help="EML Transformer data and modeling pipelines.",
)


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



# Individual pipeline stages remain top-level.
app.command("ingest")(stages.ingest)
app.command("backfill")(stages.backfill)
app.command("standardize")(stages.standardize)
app.command("scrape")(stages.scrape)
app.command("embed")(stages.embed)
app.command("build-features")(stages.build_features)
app.command("build-dataset")(stages.build_dataset)
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