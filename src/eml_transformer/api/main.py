from contextlib import asynccontextmanager
from pathlib import Path
import json
from fastapi import FastAPI, HTTPException, Query, Request

from eml_transformer.runtime import Runtime, build_runtime


@asynccontextmanager
async def lifespan(app: FastAPI):
    config_path = Path("configs/dev.yaml")
    app.state.runtime = build_runtime(config_path)
    yield


app = FastAPI(
    title="EML Data API",
    version="0.1.0",
    lifespan=lifespan,
)


def get_runtime(request: Request) -> Runtime:
    return request.app.state.runtime


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/sources")
def list_sources(request: Request) -> dict[str, list[str]]:
    runtime = get_runtime(request)
    return {"sources": runtime.source_names}


@app.get("/records")
def get_records(
    request: Request,
    source: str,
    limit: int = Query(default=100, ge=1, le=1_000),
):
    runtime = get_runtime(request)

    if source not in runtime.source_names:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown source: {source}",
        )

    # For your current unpartitioned layout:
    # data/silver/source=<source>/records.parquet
    key = runtime.paths.silver_records(source=source)

    try:
        df = runtime.storage.read_parquet(
            key,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"No Silver records found for source: {source}",
        )

    # Convert timestamps into JSON-compatible strings.
    if "published_at" in df.columns:
        df["published_at"] = df["published_at"].astype(str)

    records = json.loads(
        df.head(limit).to_json(
            orient="records",
            date_format="iso",
            date_unit="s",
        )
    )

    return {
        "source": source,
        "count": len(records),
        "records": records,
    }