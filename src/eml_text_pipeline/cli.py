import os
from pathlib import Path

import pandas as pd

import typer
from dotenv import load_dotenv

from eml_text_pipeline.ingestion.miso import MISONotificationSource
from eml_text_pipeline.ingestion.newsapi import NewsAPISource
from eml_text_pipeline.ingestion.weather_alerts import WeatherAlertSource

load_dotenv()

app = typer.Typer()

def print_ingestion_preview(df: pd.DataFrame, source: str, n: int = 3) -> None:
    typer.echo("\n" + "=" * 90)
    typer.echo(f"{source.upper()} INGESTION PREVIEW")
    typer.echo("=" * 90)

    typer.echo(f"Records retrieved: {len(df)}")
    typer.echo(f"Columns: {list(df.columns)}")

    typer.echo("\nSample records:")
    typer.echo("-" * 90)

    for i, row in df.head(n).iterrows():
        typer.echo(f"\nRecord {i + 1}")
        typer.echo(f"Title: {row.get('title')}")
        typer.echo(f"Published: {row.get('published_at')}")
        typer.echo(f"URL: {row.get('url')}")
        typer.echo("\nText snippet:")
        typer.echo((row.get("clean_text") or "")[:1000])
        typer.echo("-" * 90)

@app.command()
def ingest(
    source: str = typer.Option(...),
    output_dir: str = typer.Option("data/silver"),
    query: str = typer.Option("power markets"),
    area: str = typer.Option("IN"),
    api_key: str | None = typer.Option(None),
):
    source = source.lower()

    if source == "miso":
        ingestion_source = MISONotificationSource()

    elif source == "weather":
        ingestion_source = WeatherAlertSource(area=area)

    elif source == "newsapi":
        newsapi_key = api_key or os.getenv("NEWSAPI_KEY")

        if not newsapi_key:
            raise typer.BadParameter(
                "Missing NewsAPI key. Pass --api-key or set NEWSAPI_KEY in .env"
            )

        ingestion_source = NewsAPISource(
            api_key=newsapi_key,
            query=query,
        )

    else:
        raise typer.BadParameter(f"Unknown source: {source}")

    df = ingestion_source.run()

    output_path = Path(output_dir) / f"{source}.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # df.to_parquet(output_path, index=False)

    typer.echo(f"Retrieved {len(df)} records")
    typer.echo(f"Saved to {output_path}")

    df = df[df["title"].str.contains("New Declaration", na=False)]
    print_ingestion_preview(df, source, n=3)



@app.command()
def clean():
    print("cleaning")


if __name__ == "__main__":
    app()