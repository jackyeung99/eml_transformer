# Storage Layout

This document explains how pipeline data, processing state, model artifacts, and experiment outputs are organized.

The same logical layout is used with both supported storage backends:

- Local filesystem storage
- Amazon S3

The storage backend changes how files are accessed, but does not change how the rest of the pipeline reads and writes data.

## Storage Design

The storage system separates three concerns:

1. **Logical references** identify datasets without using physical paths.
2. **Storage paths** convert logical references into consistent locations.
3. **Storage backends** perform the actual file operations.

```text
Pipeline
    ↓
Logical Dataset Reference
    ↓
Storage Path
    ↓
Shared Read or Write Method
    ↓
Local Filesystem or Amazon S3
```

Pipeline components should not construct paths or access Amazon S3 directly. They use the shared storage interface and path helpers instead.

## Storage Backends

The project supports local and S3 storage through a shared interface.

Backend implementations provide the low-level operations required to interact with their storage system. These primitive operations may include:

- Opening a file
- Checking whether a path exists
- Listing objects
- Creating directories or parent paths
- Removing or replacing an object
- Moving or copying stored data

The implementation of these operations differs by backend.

For example:

- `LocalStorage` opens files using the local filesystem.
- `S3Storage` opens objects using an S3-compatible filesystem client.

Higher-level operations remain shared, including:

- Reading and writing JSON
- Reading and writing JSON Lines
- Reading and writing Parquet datasets
- Saving and loading model artifacts
- Reading and writing checkpoints

```text
Shared operation: write_json(...)
                       ↓
              Backend primitive: open(...)
                 ↙                 ↘
       Local filesystem          Amazon S3
```

This means a new storage backend generally needs to implement only the required primitive operations. The common serialization and dataset methods can then continue to work without being rewritten.

!!! important "Storage Responsibilities"

    Storage behavior is backend-specific, not source-specific. Data sources provide records, while the storage layer determines how those records are persisted. Source implementations should not contain local filesystem or Amazon S3 logic.

## Storage Roots

Stored outputs are divided into two primary roots:

```text
project/
├── data/
└── artifacts/
```

| Root | Purpose |
|---|---|
| `data/` | Stores Bronze, Silver, and Gold datasets along with pipeline metadata. |
| `artifacts/` | Stores trained models, model metadata, versions, and experiments. |

These are local path names. When S3 is enabled, they become prefixes within the configured bucket.

## Dataset References

Datasets are identified using logical references rather than physical paths.

A dataset reference follows this format:

```text
layer:source:artifact
```

For example:

```text
silver:eia_region:records
gold:eia_region_hourly:features
gold:load_forecasting:datasets
gold:miso_hourly_load_ridge:forecasts
```

Each reference contains three parts:

| Part | Meaning |
|---|---|
| `layer` | The medallion layer: `bronze`, `silver`, or `gold` |
| `source` | The source, feature set, dataset, or model that owns the output |
| `artifact` | The type of stored output, such as `records`, `features`, `datasets`, or `forecasts` |

Logical references keep pipeline configuration independent from the selected storage backend.

## Path Resolution

`StoragePaths` converts a dataset reference into a physical path.

Bronze and Silver datasets use the following general structure:

```text
data/{layer}/source={source}/artifact={artifact}/
```

For example:

```text
silver:eia_region:records
```

resolves to:

```text
data/silver/source=eia_region/artifact=records/
```

Gold datasets are organized by artifact type:

```text
data/gold/{artifact}/dataset={source}/
```

For example:

```text
gold:eia_region_hourly:features
```

resolves to:

```text
data/gold/features/dataset=eia_region_hourly/
```

This groups Gold outputs by their role while preserving the name of the dataset that produced them.

## Complete Folder Structure

A local storage layout may look like this:

```text
project/
├── data/
│   ├── bronze/
│   │   ├── source=eia_region/
│   │   │   └── records.jsonl
│   │   ├── source=eia_interchange/
│   │   │   └── records.jsonl
│   │   └── source=iem_afos/
│   │       └── records.jsonl
│   │
│   ├── silver/
│   │   ├── source=eia_region/
│   │   │   └── artifact=records/
│   │   │       └── part-00000.parquet
│   │   ├── source=eia_interchange/
│   │   │   └── artifact=records/
│   │   │       └── part-00000.parquet
│   │   └── source=iem_afos/
│   │       └── artifact=records/
│   │           └── part-00000.parquet
│   │
│   ├── gold/
│   │   ├── embeddings/
│   │   │   └── dataset={name}/
│   │   │       └── part-00000.parquet
│   │   ├── features/
│   │   │   └── dataset={name}/
│   │   │       └── part-00000.parquet
│   │   ├── datasets/
│   │   │   └── dataset={name}/
│   │   │       └── part-00000.parquet
│   │   └── forecasts/
│   │       └── dataset={model_name}/
│   │           └── part-00000.parquet
│   │
│   └── metadata/
│       ├── checkpoints/
│       │   └── source={source}.json
│       └── dedupe/
│           └── source={source}.json
│
└── artifacts/
    ├── models/
    │   └── model={model_name}/
    │       ├── model.joblib
    │       ├── metadata.json
    │       └── versions/
    │           └── {version}/
    │               ├── model.joblib
    │               └── metadata.json
    │
    └── experiments/
        └── experiment={experiment_name}/
```

The exact datasets present depend on the enabled sources, features, datasets, and models.

## Bronze Layout

Bronze stores raw or minimally modified source records.

```text
data/bronze/source={source}/records.jsonl
```

Examples:

```text
data/bronze/source=eia_region/records.jsonl
data/bronze/source=eia_interchange/records.jsonl
data/bronze/source=iem_afos/records.jsonl
```

Bronze records use a source-oriented layout because each file contains the original records retrieved from one external source.

JSON Lines is used because records can be appended and processed one at a time without loading the complete file into memory.

## Silver Layout

Silver stores standardized records using the general dataset structure.

```text
data/silver/source={source}/artifact=records/
```

Silver data is separated by source, but each source conforms to a shared numeric or text schema.


## Gold Layout

Gold stores derived products such as embeddings, feature sets, model-ready datasets, and forecasts.

```text
data/gold/{artifact}/dataset={name}/
```

Examples:

```text
data/gold/embeddings/dataset=iem_afos_embeddings/
data/gold/features/dataset=eia_region_hourly/
data/gold/datasets/dataset=load_forecasting/
data/gold/forecasts/dataset=miso_hourly_load_ridge/
```

Gold is organized by output type because these datasets are no longer direct representations of one external source. A Gold dataset may combine or derive information from several sources.

## Parquet Batching

Silver and Gold datasets are stored as collections of numbered Parquet files rather than as one large file.

```text
dataset/
├── part-00000.parquet
├── part-00001.parquet
└── part-00002.parquet
```

Each file contains one batch of records. Batching prevents the pipeline from loading or rewriting an entire dataset at once and makes large datasets easier to process using either local storage or Amazon S3.

The batch size is controlled by the writing operation. Part numbers are zero-padded so files remain correctly ordered when listed.

Readers treat all Parquet parts within a dataset directory as one logical dataset.


## Metadata Layout

Pipeline metadata is stored separately from Bronze, Silver, and Gold datasets.

```text
data/metadata/
├── checkpoints/
└── dedupe/
```

### Checkpoints

Checkpoints record the last successful processing position for a source.

```text
data/metadata/checkpoints/source={source}.json
```

They allow incremental ingestion to determine where a new run should begin.

A checkpoint should only advance after the associated operation completes successfully.

### Deduplication State

Deduplication files record identifiers that have already been processed.

```text
data/metadata/dedupe/source={source}.json
```

This prevents repeated records from being written during overlapping ingestion windows or repeated runs.

## Model Layout

Trained models are stored outside the dataset hierarchy under `artifacts/models/`.

```text
artifacts/models/model={model_name}/
├── model.joblib
└── metadata.json
```

| File | Purpose |
|---|---|
| `model.joblib` | Contains the serialized forecasting model. |
| `metadata.json` | Describes the model, expected inputs, training period, and evaluation results. |

The model directory is identified by the configured model name:

```text
artifacts/models/model=miso_hourly_load_ridge/
```

This keeps model artifacts separate from tabular pipeline data.

## Model Versions

Previous model versions may be retained under a model-specific `versions/` directory.

```text
artifacts/models/model={model_name}/versions/{version}/
├── model.joblib
└── metadata.json
```

The files directly under the model directory represent the currently active model:

```text
artifacts/models/model={model_name}/model.joblib
artifacts/models/model={model_name}/metadata.json
```

Versioned directories preserve earlier models for comparison, recovery, or auditing.

## Experiment Layout

Experiment outputs are stored separately from operational model artifacts.

```text
artifacts/experiments/experiment={experiment_name}/
```

Experiments may contain:

- Backtesting results
- Model comparisons
- Hyperparameter results
- Feature evaluations
- Diagnostic plots
- Experiment metadata

Separating experiments from active model artifacts prevents exploratory outputs from being confused with models used for scheduled forecasts.

## Forecast Storage

Forecasts are Gold datasets rather than model files.

```text
data/gold/forecasts/dataset={model_name}/
```

Forecast records contain predictions and identifying information such as:

- Model name
- Forecast target
- Forecast value
- Target time
- Creation time

Keeping creation and target times allows multiple forecast runs to be retained for the same future period.

The model used to generate a forecast is stored under `artifacts/models/`, while the resulting predictions are stored under `data/gold/forecasts/`.

## Path Normalization

Names used in storage paths are normalized before paths are constructed.

The current path-cleaning behavior:

- Removes surrounding whitespace
- Replaces spaces with underscores
- Replaces forward and backward slashes with hyphens
- Replaces equals signs with hyphens

This prevents component names from unintentionally creating nested paths or interfering with the partition-style naming convention.

For example:

```text
MISO Hourly/Load
```

becomes:

```text
MISO_Hourly-Load
```

## Local and S3 Equivalence

The same logical path is used with both storage backends.

A local path might be:

```text
data/gold/features/dataset=eia_region_hourly/
```

The equivalent S3 location might be:

```text
s3://{bucket}/{prefix}/data/gold/features/dataset=eia_region_hourly/
```

Only the configured storage backend and root location change. Dataset references and pipeline definitions remain the same.

## Storage Responsibility Summary

| Component | Responsibility |
|---|---|
| `DatasetRef` | Identifies a dataset using `layer:source:artifact`. |
| `StoragePaths` | Converts logical identifiers into consistent physical paths. |
| Shared storage interface | Defines the operations available to pipelines. |
| `LocalStorage` | Implements primitive operations for the local filesystem. |
| `S3Storage` | Implements primitive operations for Amazon S3. |
| Pipelines | Select what should be read or written. |
| Sources and builders | Produce records or DataFrames without managing backend-specific storage. |

## Related Documentation

- [Architecture Overview](overview.md) — Major components and their relationships
- [Data Flow](data-flow.md) — How data moves through processing stages
- [Project Structure](project-structure.md) — Organization of source code and supporting files
- [Design Principles](design-principles.md) — Reasoning behind the storage abstraction
- [Dataset References](../reference/dataset-references.md) — Exact dataset-reference rules
- [AWS Deployment](aws-deployment.md) — Use of Amazon S3 in production