# Architecture Overview

The EML Energy Forecasting Pipeline is a configuration-driven system for collecting, processing, modeling, and serving energy-market data.

It supports both numeric and textual data, including:

- Electricity demand, generation, interchange, and load forecasts
- Weather products and alerts
- Market notifications
- News and event data

The system converts external records into standardized data, derived features, model-ready datasets, trained models, and stored forecasts.

## System Architecture

The architecture consists of six major components:

| Component | Responsibility |
|---|---|
| CLI | Starts individual processing stages and multi-stage workflows. |
| Pipelines | Coordinate data processing, training, and forecasting operations. |
| Component implementations | Provide the specialized methods used by each stage, such as individual data sources, web scrapers, feature builders, dataset builders, and forecasting models. |
| Configuration | Defines enabled components, their settings, and their inputs and outputs. |
| Storage | Persists data, pipeline state, model artifacts, and forecasts. |
| API | Provides applications and users with access to stored outputs. |

## Execution Model

The CLI and API serve different purposes within the system.

Pipeline execution begins through the CLI:

```text
CLI
  ↓
Pipelines
  ↓
Processing components
  ↓
Storage
```

The CLI starts a stage or workflow. Pipelines coordinate the operation, processing components perform the specialized work, and the results are written through the storage layer.

The API provides a separate read path:

```text
Storage
  ↓
API
  ↓
External applications
```

The API reads stored data and forecasts without needing to run the processing pipelines.

Configuration supports both paths by defining the available components, storage backend, and runtime behavior.

## Processing Layers

Pipeline data is organized using a medallion architecture.

| Layer | Purpose |
|---|---|
| Bronze | Raw or minimally modified source records |
| Silver | Cleaned records converted into shared schemas |
| Gold | Embeddings, features, model-ready datasets, and forecasts |

Numeric and textual data may follow different processing steps, but both use the same general progression from source records to reusable data products.

The complete sequence of processing stages is documented in [Data Flow](data-flow.md).

## Storage Model

The system uses a shared storage interface so the same application code can operate with either local storage or Amazon S3.

Storage contains:

- Bronze, Silver, and Gold data
- Pipeline checkpoints and processing state
- Trained model artifacts and metadata
- Generated forecasts

The physical paths, dataset references, and file organization are documented in [Storage Layout](storage-layout.md).

## Configuration Model

YAML configuration files define the components used during a run and how they are connected.

Configuration controls areas such as:

- Enabled sources
- Feature and dataset definitions
- Model selection
- Training and forecast settings
- Storage backend

This allows the same pipelines to support different sources, datasets, models, and environments.

The reasoning behind this approach is documented in [Design Principles](design-principles.md). Exact configuration fields are documented in the [Configuration Schema](../reference/configuration-schema.md).

## Deployment Model

The production system separates continuous API access from scheduled pipeline execution.

- The API runs as a persistent service.
- Pipeline workflows run as scheduled or manually started tasks.
- Both use shared configuration and persistent storage.

This allows data processing and forecast generation to run only when required while keeping stored results continuously available to external applications.

The AWS services, container workloads, networking, and scheduling configuration are documented in [AWS Deployment](aws-deployment.md).

## Related Documentation

- [Data Flow](data-flow.md) — How data moves through the processing stages
- [Project Structure](project-structure.md) — Where code and supporting files belong
- [Storage Layout](storage-layout.md) — How data and artifacts are organized
- [Design Principles](design-principles.md) — Principles guiding implementation decisions
- [Testing Principles](testing-principles.md) — Testing responsibilities and strategy
- [AWS Deployment](aws-deployment.md) — Production infrastructure and execution