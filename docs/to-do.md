### 1. Restructure Pipelines (1/5 Severity)

The current implementation was developed incrementally, so each operation initially received its own pipeline class. The project did not adopt pipelines containing multiple related operations until later in development.

For example, incremental and historical ingestion were originally implemented as separate pipeline classes. Because both operations use the same sources, storage interfaces, and ingestion logic, they were later combined into a single `IngestionPipeline` with separate high-level methods for incremental ingestion and historical backfilling.

Future work should apply this type of refactoring to other closely related operations. Pipelines should group processes that share responsibilities and dependencies while exposing each operation through a clear high-level method.

This is primarily an architectural cleanup. It does not mean combining every operation into one execution path. Each subprocess should remain independently runnable through the CLI.

A proposed organization could look like this:

| Pipeline | Subprocesses | Output |
|---|---|---|
| Ingestion | `incremental`, `backfill` | Bronze source records |
| Standardization | `standardize` | Silver standardized records |
| Text Processing | `scrape`, `embed` | Enriched text and Gold embeddings |
| Dataset Preparation | `features`, `dataset` | Gold feature sets and model-ready datasets |
| Modeling | `train`, `forecast` | Model artifacts and Gold forecasts |
| Experiments | `backtest`, `evaluate`, `compare` | Metrics and research artifacts |

### 2. Generalize Feature and Dataset Construction (3/5 Severity)

The current feature and dataset modules rely on individual builder functions written for specific outputs. This works for the current datasets, but additional sources and forecasting tasks may require many similar functions that repeat selection, joining, aggregation, validation, and transformation logic.

Future work should make these modules more composable and configuration-driven. Common operations should be implemented as reusable transformations that can be combined into different feature and dataset definitions.

Reusable operations may include:

- Selecting and renaming columns
- Filtering records
- Pivoting measurements
- Joining feature sets
- Creating calendar features
- Creating lagged and rolling features
- Performing hourly or daily aggregation
- Validating keys, targets, and join relationships

Specialized builder functions should still be supported when a dataset requires custom domain logic. The goal is not to eliminate builders, but to avoid writing a new function for every minor variation of an existing transformation.

### 3. Add Incremental Standardization (4/5 Severity)

The current standardization process may reread and reprocess the complete Bronze dataset even when ingestion added only a small number of new records. This becomes increasingly inefficient as historical datasets grow, particularly when data is stored in Amazon S3.

Standardization should support separate historical and incremental behavior:

- **Historical standardization** processes all available Bronze batches when rebuilding a Silver dataset.
- **Incremental standardization** processes only Bronze batches added since the last successful standardization run.

The pipeline should track which Bronze batches have already been standardized and write only the new standardized records to Silver.

A checkpoint should advance only after the corresponding Silver output has been written successfully. The design should also account for retries, overlapping ingestion windows, and duplicate records so interrupted runs can be repeated safely.

This change will reduce:

- S3 reads
- Processing time
- Memory usage
- Repeated transformations
- Unnecessary Silver rewrites

### 4. Rework Scraping for Shared Storage and AWS (4/5 Severity)

The existing scraping implementation should be updated to use the shared storage abstraction instead of depending on local file paths or assumptions from the earlier pipeline structure.

Scraping inputs and outputs should be identified using `DatasetRef` values. The pipeline should use `StoragePaths` and the configured storage backend to resolve those references.

For example:

```text
silver:gdelt:records
    ↓
Text scraping
    ↓
silver:gdelt:enriched_records
```

The scraping pipeline should work the same way with:

- Local filesystem storage
- Amazon S3
- Historical datasets
- Incrementally added batches

The current scraping logic can continue to handle source-specific URL retrieval and content extraction, but storage access should be moved out of the scraper implementation.

The intended separation is:

```text
Scraping pipeline
    → reads input through storage
    → calls the source-specific scraping implementation
    → writes enriched output through storage
```

The source-specific scraper should receive records and return enriched records without needing to know whether they came from a local file or an S3 object.

The refactor should also add or verify:

- Batched reading and writing
- Incremental processing of new Silver records
- Retry and timeout handling
- Per-record failure handling
- Scraping progress logs
- Output and failure counts
- Checkpoints that advance only after successful writes
- Safe operation within temporary ECS task storage

This will allow scraping to run consistently during local development and as an ECS task in AWS while following the same dataset-reference conventions as the rest of the pipeline.