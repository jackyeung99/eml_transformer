# EML Energy Forecasting Pipeline

A configuration-driven pipeline for collecting, standardizing, transforming, and preparing energy-market data for forecasting and research.

The project supports both textual and numeric data, including electricity-system measurements, grid notifications, weather alerts, and news. It provides the infrastructure needed to move data from external sources into reproducible, model-ready datasets and forecasts.

## What This Repository Contains

This repository provides infrastructure for:

- Collecting textual and numeric data from external sources
- Preserving raw source data
- Standardizing records into shared schemas
- Generating text embeddings
- Building forecasting features
- Combining features into model-ready datasets
- Training and evaluating supported forecasting models
- Generating and storing forecasts
- Serving forecast results through an API
- Running pipelines locally or with cloud storage


## Important: Forecasting Models

> The models currently included in this repository are placeholders used to test the complete training and forecasting workflow. They are **not production forecasting models**.
>
> This repository primarily provides the data pipelines, modeling interfaces, and infrastructure needed to develop and evaluate forecasting models. Trained model files are created at runtime and stored locally or in Amazon S3 rather than committed to this repository.
# Overview

![EML Energy Forecasting Pipeline](docs/eml-energy-forecasting-pipeline.png)


The system processes data through a series of independently executable stages:


The stages are configuration-driven. A configuration file determines which sources, feature builders, dataset builders, and models are enabled without requiring changes to the pipeline code.

## Data Sources

Supported sources include textual data such as:

* MISO notifications
* National Weather Service products and alerts
* GDELT news data
* NewsAPI articles

The pipeline also supports numeric energy data such as:
* Electricity demand
* Demand forecasts
* Net generation
* Interchange between balancing authorities

Not every source is enabled by default. Enabled sources and their settings are controlled through the selected configuration file.

# Quick Start

## 1. Clone the Repository

```bash
git clone https://github.com/jackyeung99/eml_transformer.git
cd eml_transformer
```

## 2. Install the Project

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), and then run:

```bash
uv python install 3.10
uv sync
```

`uv sync` creates a local `.venv` environment and installs the project and its development dependencies.

## 3. Install Optional Dependencies

Install notebook and visualization dependencies:

```bash
uv sync --group notebook
```

Install embedding dependencies:

```bash
uv sync --extra embeddings
```

Install both groups:

```bash
uv sync --group notebook --extra embeddings
```

## 4. Configure Environment Variables

Create a `.env` file in the repository root.

Add the API keys required by the sources you plan to use:

```env
EIA_API_KEY=your_eia_key
NEWSAPI_KEY=your_newsapi_key
```

Do not commit the `.env` file or place API keys directly in YAML configuration files.

Configuration files refer to the names of environment variables. The corresponding values are resolved when the application runs.

## 5. Inspect the Configuration

View the sources available in the selected configuration:

```bash
uv run eml_transformer inspect sources
```

Use the CLI help command to see all available commands:

```bash
uv run eml_transformer --help
```

You can also inspect help for a specific command:

```bash
uv run eml_transformer ingest --help
```

# Running the Pipeline

The command-line interface provides two ways to run the pipeline:

- **Stages** run one processing step at a time.
- **Workflows** run multiple related stages in the correct order.

## Stages

Stages are useful for development, debugging, and rerunning a specific part of the pipeline.

Available stages include:

```text
ingest → standardize → embed
                    ↘ build-features → build-datasets → model
```

For example, run incremental ingestion for one source:

```bash
uv run eml_transformer ingest \
    --source eia_region \
    --config configs/dev.yaml
```

Run historical ingestion for a supported source:

```bash
uv run eml_transformer backfill \
    --source iem_afos \
    --from-date 2026-04-20 \
    --to-date 2026-05-20 \
    --window-days 7 \
    --config configs/dev.yaml
```

Run standardization separately:

```bash
uv run eml_transformer standardize \
    --source eia_region \
    --config configs/dev.yaml
```

## Workflows

Workflows combine multiple stages into a complete process. They are useful for routine execution because they pass data through the required stages without requiring each command to be run manually.

For example, an ingestion workflow may run:

```text
ingest → standardize
```

A complete forecasting workflow may run:

```text
ingest → standardize → build features → build datasets → train → forecast
```

Use the CLI help command to view the currently available stages and workflows:

```bash
uv run eml_transformer --help
```

Detailed commands and options are documented in `docs/guides/cli-reference.md`.

# Storage

The project supports local filesystem storage for development and Amazon S3 storage for deployed environments.

The storage backend is selected through configuration and manages two main types of output:

- **Data** contains records produced by the pipeline.
- **Artifacts** contains generated files used by the application, such as trained models and model metadata.

A simplified local storage layout is:

```text
artifacts/
└── models/
    └── <model-name>/
        ├── model.joblib
        └── metadata.json

data/
├── bronze/
├── silver/
└── gold/
    ├── embeddings/
    ├── features/
    ├── datasets/
    └── forecasts/
```
The data/ directory contains records produced by the pipeline:

Bronze contains raw source records.
Silver contains cleaned and standardized records.
Gold contains derived outputs such as embeddings, features, modeling datasets, and forecasts.

The artifacts/ directory contains files generated by the modeling pipeline, including serialized models, training metadata, validation metrics, diagnostics, hyperparameters, and training settings.

Model artifacts are created at runtime and should not be committed to Git. During local development, they are stored in the local filesystem. In a deployed environment, they can be stored in Amazon S3.

Dataset locations are generated from dataset references. For example:

```text
silver:eia_region:records
```

This reference identifies the standardized Silver records produced from the eia_region source.

See the storage-layout documentation for complete path, dataset-reference, and artifact-naming conventions.

# Configuration

Pipeline behavior is defined through YAML configuration.

Configuration controls:

* Storage backend and location
* Enabled data sources
* Source-specific API settings
* Feature builders
* Dataset builders
* Embedding settings
* Forecasting models
* Training windows
* Forecast horizons
* Model output locations

The code defines how a pipeline stage behaves. Configuration determines which components run and which settings they receive.

See `docs/guides/configuration.md` for a complete explanation.

# Testing

Run the complete test suite with:

```bash
uv run pytest
```

Run a specific test directory or file:

```bash
uv run pytest tests/unit
uv run pytest tests/unit/sources
```

Tests should not require access to live APIs or production storage unless they are explicitly marked as integration tests.

# Documentation

Detailed documentation is available in `docs/`.

Recommended starting points:

* `docs/index.md` — documentation homepage
* `docs/architecture/overview.md` — high-level system explanation
* `docs/architecture/data-flow.md` — how data moves through the pipeline
* `docs/architecture/design-principles.md` — principles guiding the design
* `docs/architecture/project-structure.md` — repository and package organization
* `docs/guides/local-setup.md` — complete local setup instructions
* `docs/guides/configuration.md` — configuration guide
* `docs/guides/cli-reference.md` — command-line reference

# Project Status

This project is under active development.

Interfaces, configuration fields, commands, and storage conventions may continue to evolve as deployment and forecasting workflows are finalized.
