# Project Structure

This document explains how the EML Energy Forecasting Pipeline repository is organized and where each type of code, configuration, data, and documentation belongs.

## Overview

The repository separates reusable application code from configuration, stored data, model artifacts, documentation, exploratory notebooks, utility scripts, and automated tests.

The repository contains two broad categories of directories:

1. **Supporting project directories** contain configuration, data, documentation, notebooks, scripts, artifacts, and tests.
2. **The source package** contains the reusable Python code that implements the pipeline, API, storage system, and forecasting functionality.

```text
project/
├── artifacts/       # Generated model artifacts
├── configs/         # Runtime configuration
├── data/            # Locally stored pipeline data
├── docs/            # Project documentation
├── notebooks/       # Exploration and analysis
├── scripts/         # Standalone utilities
├── tests/           # Automated tests
└── src/             # Production Python source code
    └── eml_transformer/
```

## Supporting Project Directories


### `artifacts/`

The `artifacts/` directory stores generated modeling artifacts when the project uses local storage.

These artifacts may include:

- Trained models
- Model metadata
- Evaluation metrics
- Training information
- Other files required to reproduce forecasts

```text
artifacts/
└── models/
```

In AWS deployments, equivalent artifacts can be stored in Amazon S3 instead of the local directory.

Generated artifacts should not be treated as source code or committed to version control unless a specific artifact is intentionally included as an example.

### `configs/`

The `configs/` directory contains YAML files that control pipeline behavior.

```text
configs/
├── dev.yaml
├── prod.yaml
└── ...
```

Configuration files define components such as:

- Storage backends and locations
- Enabled data sources
- Source-specific settings
- Embedding processes
- Feature builders
- Dataset builders
- Forecasting models
- Training settings
- Forecast settings

Keeping these settings outside the source code allows the same application to run in different environments without changing its implementation.

For example, a development configuration may use local storage, while a production configuration may use Amazon S3.

See the [Configuration Guide](../guides/configuration.md) for instructions and the [Configuration Schema](../reference/configuration-schema.md) for exact field definitions.

### `data/`

The `data/` directory stores pipeline data when the project uses local storage.

```text
data/
├── bronze/
├── silver/
├── gold/
└── metadata/
```

In AWS deployments, these data products can be stored in Amazon S3 using the same logical organization.

See [Storage Layout](../architecture/storage-layout.md) for an explanation on the specifc file structure 

### `docs/`

The `docs/` directory contains the project documentation.

### `notebooks/`

The `notebooks/` directory contains Jupyter notebooks used for exploration, analysis, visualization, and debugging.

Notebooks are useful for:

- Inspecting source data
- Exploring pipeline outputs
- Testing modeling ideas
- Visualizing time series
- Investigating data-quality problems
- Comparing model results

Reusable production logic should be moved into the main Python package rather than remaining inside a notebook.

### `scripts/`

The `scripts/` directory contains standalone utility and maintenance scripts that do not belong in the primary command-line interface.

Scripts may be used for:

- One-time data migrations
- Specialized backfills
- Operational maintenance
- Development utilities
- Temporary validation tasks

Frequently used or production-critical operations should generally be implemented through the main command-line interface instead.


### `tests/`

The `tests/` directory contains automated tests for the project.

```text
tests/
├── unit/
├── integration/
└── ...
```

Tests may cover:

- Configuration loading
- Dataset-reference parsing
- Storage path generation
- Source clients and parsing
- Record standardization
- Feature calculations
- Dataset joins
- Timezone handling
- Model training and forecasting
- API endpoints
- Complete pipeline stages

Unit tests validate isolated behavior. Integration tests verify that multiple components work together correctly.


## Production Source Code

The `src/` directory contains the installable Python package. Using a `src` layout separates importable application code from configuration, data, documentation, notebooks, scripts, and tests.

```text
src/
└── eml_transformer/
```

The pipeline’s core logic is organized into modules based on functionality.

| Directory | Responsibility |
|---|---|
| `api/` | Defines the FastAPI application and endpoints for accessing records, datasets, models, and forecasts. |
| `cli/` | Provides commands for running pipeline stages, workflows, and inspection tools. |
| `config/` | Loads and validates YAML configuration and defines the project’s configuration structures. |
| `datasets/` | Combines feature sets into model-ready datasets. |
| `embeddings/` | Converts standardized text records into numeric vector embeddings. |
| `features/` | Creates reusable hourly, daily, calendar, lagged, and other forecasting features. |
| `ingestion/` | Collects external data and converts source-specific responses into shared record formats. |
| `modeling/` | Defines forecasting models, training and evaluation logic, and model artifacts. |
| `pipelines/` | Coordinates processing stages by connecting configuration, storage, and component implementations. |
| `storage/` | Reads and writes data and artifacts using local storage or Amazon S3. |
| `utils/` | Provides shared helpers for timestamps, dates, hashing, validation, and other common operations. |

The exact files within each area may change as the project develops, but each directory should retain a clear responsibility.


### Commond Module Patterns


Several packages use similar file types to separate high-level responsibilities.

| Pattern | Responsibility |
|---|---|
| `pipeline.py` | Coordinates configuration, storage, and component implementations for a processing stage. |
| `base.py` | Defines a shared interface for interchangeable implementations, such as forecasting models or storage backends. |
| `registry.py` | Maps names used in configuration to their corresponding Python implementations. |
| `schemas.py` | Defines shared record structures and data contracts used between components. |
| `results.py` | Defines structured pipeline results used to communicate run status, outputs, record counts, and errors to callers such as the CLI. A separate file is most useful when a package contains multiple pipelines or result types. |


Not every package uses every pattern. Individual packages may contain additional files and subdirectories that support their specific functionality, such as builders, transformations, source clients, or model implementations.

In general, pipelines coordinate execution, registries select implementations, and specialized components perform the underlying work.
## Root-Level Files

### `README.md`

The README provides the main introduction to the repository.

It should contain:

- Project purpose
- Major capabilities
- Basic installation
- Quick-start commands
- Links to the full documentation

Detailed explanations should remain in `docs/` rather than being duplicated in the README.

### `pyproject.toml`

The `pyproject.toml` file defines the Python project.

It contains information such as:

- Package metadata
- Python version requirements
- Runtime dependencies
- Optional dependency groups
- Command-line entry points
- Build configuration
- Development-tool settings

### `uv.lock`

The `uv.lock` file records the exact resolved dependency versions used by the project.

It allows local development, testing, and container builds to install consistent dependency versions.

### `Dockerfile`

The Dockerfile defines the application container used for AWS deployment.

The same image can support multiple workloads by supplying different commands, including:

- The persistent FastAPI service
- Scheduled pipeline workflows
- Manually started ECS tasks

### `.gitignore`

The `.gitignore` file identifies local or generated files that should not be committed.

These commonly include:

- Local data
- Trained model artifacts
- Environment files
- Python caches
- Notebook checkpoints
- Test caches
- Build outputs

### `.dockerignore`

The `.dockerignore` file prevents unnecessary local files from being copied into the Docker build context.

This helps keep the container image smaller and avoids including items such as:

- Local datasets
- Model artifacts
- Notebooks
- Git metadata
- Development caches
- Temporary files

## Summary and Placement Guidelines

The repository is organized around clearly defined responsibilities, making the project easier to maintain and extend.

Supporting files, production code, data processing, forecasting, deployment, and documentation remain separate while sharing common configuration, storage, and runtime components.

When adding a new component, place it in the directory that most closely matches its primary responsibility:

| Item | Location |
|---|---|
| Runtime setting | `configs/` |
| Raw or processed local data | `data/` |
| Trained local model | `artifacts/` |
| Conceptual system explanation | `docs/architecture/` |
| Step-by-step instructions | `docs/guides/` |
| Source-specific documentation | `docs/sources/` |
| Pipeline-stage documentation | `docs/pipelines/` |
| Operational instructions | `docs/operations/` |
| Exact technical definitions | `docs/reference/` |
| Architecture decision | `docs/decisions/` |
| Exploratory analysis | `notebooks/` |
| One-time utility | `scripts/` |
| Reusable application logic | `src/eml_transformer/` |
| Automated validation | `tests/` |
