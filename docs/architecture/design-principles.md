# Design Principles

## Overview

The EML Energy Forecasting Pipeline is designed as a reusable and extensible system rather than a collection of one-time scripts.

Its design is guided by the following principles:

- Keep components modular and interchangeable
- Separate orchestration from implementation
- Control behavior through configuration
- Preserve reproducibility and traceability
- Maintain clear boundaries between responsibilities
- Support extension without rewriting existing workflows
- Preserve source data so it can be reprocessed
- Validate components independently through testing

These principles introduce more structure than a small single-script project, but provide a stronger foundation for continued development, experimentation, and collaboration.

## Modularity and Interchangeable Components

Modularity is the primary focus of the system.

Sources, feature builders, dataset builders, storage backends, and forecasting models can be added or replaced without changing the core pipeline logic.

Configuration determines which components should run, while registries map configured names to their Python implementations. Pipelines coordinate these components through consistent interfaces rather than depending directly on a specific implementation.

For example, one configuration may train Model A using Dataset A, while another trains Model B using Dataset B. Both can use the same training and forecasting pipelines without requiring changes to their orchestration logic.

This makes it easier to:

- Compare models and datasets
- Add new implementations
- Reuse processing stages
- Run alternative experimental configurations
- Change storage backends
- Extend the system without disrupting existing components

## Separation of Orchestration and Implementation

The system separates the code that starts and coordinates work from the code that performs specialized operations.

The intended execution structure is:

```text
CLI
  ↓
Pipelines
  ↓
Specialized components
  ↓
Storage
```

Each layer has a distinct responsibility:

- The CLI accepts commands and presents results.
- Pipelines coordinate configuration, storage, and execution.
- Specialized components perform ingestion, transformation, dataset construction, or modeling.
- The storage layer manages the persistence of data and artifacts.

This separation prevents command-line code and pipelines from becoming tightly coupled to individual sources, transformations, or models.

## Configuration-Driven Behavior

Runtime behavior is controlled through YAML configuration instead of being hard-coded into application entry points.

Configuration can define:

- Enabled data sources
- Source-specific parameters
- Storage settings
- Feature and dataset builders
- Model types
- Selected features and targets
- Training settings
- Forecast settings

This allows the same application code to support different environments, datasets, models, and experiments.

Configuration files also provide a record of how a particular workflow or experiment was defined, making previous runs easier to understand and reproduce.

## Clear Responsibility Boundaries

Each component should focus on a clearly defined responsibility.

For example:

- Source implementations retrieve and interpret external data.
- Standardization converts source responses into shared schemas.
- Feature builders create reusable derived variables.
- Dataset builders combine features into model-ready tables.
- Model implementations fit models and generate predictions.
- Pipelines coordinate these operations.
- Storage implementations read and write data and artifacts.

A component should not take on responsibilities that belong to another layer. For example, a feature builder should not construct S3 paths, and a CLI command should not implement feature engineering.

These boundaries make components easier to understand, test, reuse, and replace.

## Reproducibility and Traceability

The system should make it possible to determine how a dataset, model, or forecast was produced.

Reproducibility is supported by preserving:

- Raw source records
- Standardized and derived data products
- Configuration settings
- Model metadata
- Training and validation information
- Pipeline checkpoints
- Forecast creation times

This is particularly important for research and forecasting because source data, preprocessing methods, model settings, and external APIs may change over time.

Reproducibility does not mean that every external response can always be recreated exactly. Instead, the system preserves enough data and metadata to trace and repeat its own processing behavior whenever practical.

## Preservation of Raw Data

Raw source responses are stored before standardization whenever practical.

Preserving raw data allows records to be processed again when:

- Standardization logic changes
- A transformation bug is discovered
- New fields become useful
- A different downstream task requires another representation
- Historical data is no longer available from the source

This reduces dependence on external APIs and protects against rate limits, changing responses, and limited historical access.

The detailed movement of data through Bronze, Silver, and Gold is documented in [Data Flow](data-flow.md).

## Shared Data Contracts

External sources frequently use different field names, formats, and response structures.

The system converts source-specific data into shared record schemas before it reaches downstream components. These schemas act as contracts between stages.

Shared contracts allow later stages to operate consistently without understanding the original format of every source. For example, embedding generation can process standardized text records regardless of whether they originated from weather products, market notifications, or news articles.

Interfaces and schemas also make assumptions more explicit and reduce coupling between components.

## Extensibility

New functionality should fit into the existing architecture without requiring unrelated components to be rewritten.

A typical extension involves:

1. Implementing a new component.
2. Following the appropriate shared interface or data contract.
3. Registering the implementation under a stable name.
4. Selecting it through configuration.

This pattern can support future additions such as:

- New energy-market or weather sources
- Alternative feature-building methods
- Additional model-ready datasets
- New embedding models
- Statistical, machine-learning, or probabilistic forecasts
- Additional storage implementations

Extensibility does not mean anticipating every future requirement. It means maintaining boundaries that allow new functionality to be introduced with limited impact on existing code.

## Consistency Without Unnecessary Uniformity

Similar components should follow consistent conventions, but every package does not need to have an identical file structure.

For example, packages may commonly use:

- `base.py` for shared interfaces
- `registry.py` for implementation lookup
- `pipeline.py` for orchestration
- `schemas.py` for shared data structures
- `results.py` for multiple pipeline result types

A smaller package may keep related definitions together, while a larger package may separate them into additional files or subdirectories.

The goal is consistent responsibilities and behavior, not creating files solely to make every package look the same.

## Testable Components

Clear boundaries should make components independently testable.

Specialized logic should be kept outside the CLI and high-level orchestration whenever practical. This allows transformations, builders, storage behavior, and model implementations to be tested without running an entire workflow.

Testing expectations and organization are documented separately in [Testing Principles](testing-principles.md).

## Practical Complexity

The architecture intentionally includes more structure than a small project containing only `main.py` and `utils.py`.

That additional structure is justified when it provides a clear benefit, such as:

- Supporting interchangeable implementations
- Isolating source-specific behavior
- Preserving reusable transformations
- Improving testability
- Enabling configuration-driven experiments
- Supporting local and cloud execution

Structure should not be added only for appearance or theoretical flexibility. New abstractions should solve an existing problem or support a realistic extension of the system.

## Summary

The central design principle is that the pipeline should remain stable while its individual components can evolve.

```text
Use configuration to select behavior.
Use registries to resolve implementations.
Use pipelines to coordinate execution.
Use specialized components to perform the work.
Use shared interfaces and schemas to define boundaries.
Use storage and metadata to preserve traceability.
```

Together, these principles support a system that is modular, reproducible, maintainable, and capable of growing alongside future forecasting and research requirements.