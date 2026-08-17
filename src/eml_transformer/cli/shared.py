from __future__ import annotations

from typing import Any

import pandas as pd
import typer


DEFAULT_CONFIG = "configs/dev.yaml"


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
    typer.echo(
        frame.to_string(
            index=False,
            max_colwidth=40,
        )
    )
    typer.echo("=" * 100 + "\n")


def exit_on_failure(results: list[Any]) -> None:
    if any(
        getattr(result, "status", None) == "failure"
        for result in results
    ):
        raise typer.Exit(1)