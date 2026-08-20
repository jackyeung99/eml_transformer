### 1. Restructure Pipelines   (1/5 Severity)

The current implementation was developed incrementally, so each operation initially received its own pipeline class. The project did not adopt pipelines containing multiple related operations until later in development.

For example, incremental and historical ingestion were originally implemented as separate pipeline classes. Because both operations use the same sources, storage interfaces, and ingestion logic, they were later combined into a single IngestionPipeline with separate high-level methods for incremental ingestion and historical backfilling.

Future work should apply this type of refactoring to other closely related operations. Pipelines should group processes that share responsibilities and dependencies while exposing each operation through a clear high-level method.

This is primarily an architectural cleanup. It does not mean combining every operation into one execution path. Each subprocess should remain independently runnable through the CLI.

A proposed refactor could look like something like this. 

| Pipeline | Subprocesses | Output |
|---|---|---|
| Ingestion | `incremental`, `backfill` | Bronze source records |
| Standardization | `standardize` | Silver normalized records |
| Text Processing | `scrape`, `embed` | Enriched text and Gold embeddings |
| Dataset Preparation | `features`, `dataset` | Gold feature sets and model-ready datasets |
| Modeling | `train`, `forecast` | Model artifacts and Gold forecasts |
| Experiments | `backtest`, `evaluate`, `compare` | Metrics and research artifacts |