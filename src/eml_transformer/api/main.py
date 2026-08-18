from __future__ import annotations

import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request

from eml_transformer.runtime import Runtime, build_runtime


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.runtime = build_runtime(Path("configs/dev.yaml"))
    yield


app = FastAPI(
    title="EML Data API",
    version="0.2.0",
    lifespan=lifespan,
)


def get_runtime(request: Request) -> Runtime:
    return request.app.state.runtime


def _definitions(runtime: Runtime, attribute: str) -> dict[str, Any]:
    definitions = getattr(runtime.config, attribute, {})
    return definitions if isinstance(definitions, dict) else {}


def _get_definition(
    runtime: Runtime,
    attribute: str,
    name: str,
    resource: str,
) -> Any:
    definition = _definitions(runtime, attribute).get(name)
    if definition is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown {resource}: {name}",
        )
    return definition


def _records_response(
    frame: pd.DataFrame,
    *,
    limit: int,
    offset: int,
) -> tuple[int, list[dict[str, Any]]]:
    total = len(frame)
    page = frame.iloc[offset : offset + limit]
    records = json.loads(
        page.to_json(
            orient="records",
            date_format="iso",
            date_unit="s",
        )
    )
    return total, records


def _read_dataset(
    runtime: Runtime,
    ref: str,
    resource_description: str,
) -> pd.DataFrame:
    started_at = time.monotonic()
    try:
        frame = runtime.storage.read_dataset(ref)
    except Exception as error:
        logger.exception(
            "Dataset read failed | resource=%s ref=%s",
            resource_description,
            ref,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read {resource_description}",
        ) from error

    if frame.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No records found for {resource_description}",
        )

    logger.info(
        "Dataset read completed | resource=%s ref=%s rows=%s seconds=%.2f",
        resource_description,
        ref,
        len(frame),
        time.monotonic() - started_at,
    )
    return frame


def _model_path(runtime: Runtime, model_output: str) -> str:
    # StoragePaths owns the physical layout of model artifacts.
    return runtime.paths.model(model_output)


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
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    runtime = get_runtime(request)
    if source not in runtime.source_names:
        raise HTTPException(404, f"Unknown source: {source}")

    ref = f"silver:{source}:records"
    frame = _read_dataset(runtime, ref, f"source {source}")
    total, records = _records_response(frame, limit=limit, offset=offset)
    return {
        "source": source,
        "total": total,
        "count": len(records),
        "offset": offset,
        "limit": limit,
        "records": records,
    }


@app.get("/datasets")
def list_datasets(request: Request) -> dict[str, list[dict[str, Any]]]:
    runtime = get_runtime(request)
    datasets = [
        {
            "name": name,
            "enabled": definition.enabled,
            "output": definition.output,
        }
        for name, definition in _definitions(runtime, "datasets").items()
    ]
    return {"datasets": datasets}


@app.get("/datasets/{dataset_name}")
def get_dataset(
    request: Request,
    dataset_name: str,
    limit: int = Query(default=100, ge=1, le=10_000),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    runtime = get_runtime(request)
    definition = _get_definition(
        runtime, "datasets", dataset_name, "dataset"
    )
    frame = _read_dataset(runtime, definition.output, f"dataset {dataset_name}")
    total, records = _records_response(frame, limit=limit, offset=offset)
    return {
        "dataset": dataset_name,
        "reference": definition.output,
        "total": total,
        "count": len(records),
        "offset": offset,
        "limit": limit,
        "records": records,
    }


@app.get("/models")
def list_models(request: Request) -> dict[str, list[dict[str, Any]]]:
    runtime = get_runtime(request)
    models = [
        {
            "name": name,
            "enabled": definition.enabled,
            "model_type": definition.model_type,
            "model_output": definition.model_output,
            "forecast_output": definition.forecast_output,
        }
        for name, definition in _definitions(runtime, "modeling").items()
    ]
    return {"models": models}


@app.get("/models/{model_name}")
def get_model(request: Request, model_name: str) -> dict[str, Any]:
    runtime = get_runtime(request)
    definition = _get_definition(runtime, "modeling", model_name, "model")
    metadata = runtime.storage.read_model_metadata(
        _model_path(runtime, definition.model_output)
    )
    if metadata is None:
        raise HTTPException(404, f"No trained artifact found for model: {model_name}")

    return {
        "model": model_name,
        "model_type": definition.model_type,
        "metadata": metadata.to_dict(),
    }


@app.get("/models/{model_name}/parameters")
def get_model_parameters(request: Request, model_name: str) -> dict[str, Any]:
    runtime = get_runtime(request)
    definition = _get_definition(runtime, "modeling", model_name, "model")
    metadata = runtime.storage.read_model_metadata(
        _model_path(runtime, definition.model_output)
    )
    if metadata is None:
        raise HTTPException(404, f"No trained artifact found for model: {model_name}")

    return {
        "model": model_name,
        "model_version": metadata.model_version,
        "hyper_parameters": metadata.hyper_parameters,
        "training_settings": metadata.training_settings,
        "features": list(metadata.features),
        "target": metadata.target,
        "metrics": metadata.metrics,
        "diagnostics": metadata.diagnostics,
    }


@app.get("/models/{model_name}/forecasts")
def get_forecasts(
    request: Request,
    model_name: str,
    limit: int = Query(default=100, ge=1, le=10_000),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    runtime = get_runtime(request)
    definition = _get_definition(runtime, "modeling", model_name, "model")
    frame = _read_dataset(
        runtime,
        definition.forecast_output,
        f"forecasts for model {model_name}",
    )

    sort_columns = [
        column
        for column in ("target_time", "created_at")
        if column in frame.columns
    ]
    if sort_columns:
        frame = frame.sort_values(sort_columns, ascending=False)

    total, records = _records_response(frame, limit=limit, offset=offset)
    return {
        "model": model_name,
        "reference": definition.forecast_output,
        "total": total,
        "count": len(records),
        "offset": offset,
        "limit": limit,
        "forecasts": records,
    }