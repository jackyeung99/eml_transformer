# EML Energy Forecasting Pipeline Documentation

Welcome to the documentation for the EML Energy Forecasting Pipeline.

This project collects, processes, and organizes energy-market data for forecasting and research. It supports textual and numeric sources, feature engineering, dataset creation, model training workflows, forecast storage, and API access.

## Where to Start

If this is your first time working with the project, read the documentation in this order:

1. [Architecture Overview](architecture/overview.md)
2. [Data Flow](architecture/data-flow.md)
3. [Local Setup](guides/local-setup.md)
4. [Configuration Guide](guides/configuration.md)
5. [CLI Guide](guides/cli-reference.md)
6. [Visual Diagram](eml-energy-forecasting-pipeline.png)

These pages explain what the project does, how data moves through it, and how to run it locally.

## Documentation Sections

### Architecture

The architecture documentation explains how the complete system is designed and how its major components work together.

- [Architecture Overview](architecture/overview.md) — A high-level introduction to the system
- [Data Flow](architecture/data-flow.md) — How data moves from external sources to forecasts
- [Design Principles](architecture/design-principles.md) — The principles guiding the project
- [Project Structure](architecture/project-structure.md) — How the repository and Python packages are organized
- [Storage Layout](architecture/storage-layout.md) — How data and artifacts are stored
- [AWS Deployment](architecture/aws-deployment.md) — How the system is deployed in AWS

### Guides

Guides provide step-by-step instructions for completing common tasks.

- [Local Setup](guides/local-setup.md) — Install and run the project locally
- [Configuration](guides/configuration.md) — Configure storage, sources, features, datasets, and models
- [CLI Reference](guides/cli-reference.md) — Run stages and workflows from the command line
- [Adding a Source](guides/adding-a-source.md) — Add a new external data source
- [Adding a Feature](guides/adding-a-feature.md) — Add a feature-building process
- [Adding a Dataset](guides/adding-a-dataset.md) — Add a model-ready dataset
- [Adding a Model](guides/adding-a-model.md) — Add a forecasting model implementation

### Data Sources

Source documentation explains what each external data source provides and how it is processed.

- [Source Catalog](sources/index.md) — Overview of all supported sources
- [EIA Region](sources/eia-region.md) — Regional electricity demand, forecasts, and generation
- [EIA Interchange](sources/eia-interchange.md) — Electricity interchange between balancing authorities
- [IEM AFOS](sources/iem-afos.md) — Archived National Weather Service products
- [MISO Notifications](sources/miso-notifications.md) — MISO operational notifications
- [GDELT](sources/gdelt.md) — News and event data
- [NewsAPI](sources/newsapi.md) — News article data
- [Weather Alerts](sources/weather-alerts.md) — National Weather Service alerts

### Pipelines

Pipeline documentation explains how each processing stage works.

- [Ingestion](pipelines/ingestion.md) — Collect data and write Bronze records
- [Standardization](pipelines/standardization.md) — Convert Bronze records into shared Silver schemas
- [Embeddings](pipelines/embeddings.md) — Convert text into numeric vectors
- [Features](pipelines/features.md) — Build forecasting features
- [Datasets](pipelines/datasets.md) — Combine features into model-ready datasets
- [Modeling](pipelines/modeling.md) — Train, evaluate, and run forecasting models

### Reference

Reference documentation provides exact technical definitions and formats.

- [Schemas](reference/schemas.md) — Record, dataset, forecast, and metadata fields
- [Dataset References](reference/dataset-references.md) — Dataset naming and path conventions
- [Configuration Schema](reference/configuration-schema.md) — Supported configuration fields and values
- [API Reference](reference/api.md) — Forecast API endpoints and responses


### Operations

Operations documentation explains how to run and maintain the deployed system.

- [Workflows](operations/workflows.md) — Multi-stage execution flows
- [Scheduling](operations/scheduling.md) — Automated workflow schedules
- [Logging](operations/logging.md) — Log configuration and interpretation
- [Monitoring](operations/monitoring.md) — Data, model, forecast, and API health
- [Troubleshooting](operations/troubleshooting.md) — Common failures and recovery steps

### Architecture Decisions

Architecture Decision Records explain why important technical choices were made.

- [Medallion Architecture](decisions/001-medallion-architecture.md)
- [Storage Abstraction](decisions/002-storage-abstraction.md)
- [Model Training Strategy](decisions/003-model-training-strategy.md)

## Documentation Conventions

Throughout the documentation:

- **Bronze** refers to raw or minimally modified source records.
- **Silver** refers to cleaned and standardized records.
- **Gold** refers to derived embeddings, features, datasets, and forecasts.
- **Stage** refers to one independently executable processing step.
- **Workflow** refers to multiple stages executed in sequence.
- **Artifact** refers to a generated file such as a trained model or its metadata.
- **Dataset reference** refers to a logical dataset identifier such as `silver:eia_region:records`.

## Project Status

This project is under active development. Commands, configuration fields, storage conventions, and documentation may change as the forecasting and AWS deployment workflows are finalized.