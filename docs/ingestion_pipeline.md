# Ingestion Pipeline

## Overview

The goal of the ingestion pipeline is to create a robust and reproducible framework for gathering, storing, and preprocessing textual data from multiple external sources for downstream modeling and analysis.

The pipeline is designed around a medallion-style architecture:

```text
Bronze -> Silver -> Gold
```

Each layer has an independent purpose:

- **Bronze** stores raw source data exactly as retrieved.
- **Silver** standardizes and cleans records into a consistent schema.
- **Gold** prepares modeling-ready datasets such as embeddings.

This separation improves:
- reproducibility
- debugging
- source traceability
- incremental updates
- downstream flexibility

# Pipeline Stages

## 1. Raw Ingestion (Bronze Layer)

The bronze layer is responsible for collecting raw data from multiple external sources and storing the original responses without modification.

To support many different providers consistently, the ingestion system uses a shared source abstraction. Each source implements the same high-level interface while handling its own API logic internally.

Examples of sources include:

- MISO notifications
- NewsAPI articles
- National Weather Service alerts

Even though these sources return different response formats, they all follow the same ingestion workflow:

```python
fetch_raw()
parse_records()
standardize_records()
```

This abstraction allows the pipeline to:
- reuse ingestion logic across sources
- simplify adding new data providers
- maintain a consistent downstream schema
- separate source-specific logic from pipeline orchestration

### Goals

- Preserve original source responses
- Support reproducibility and auditing
- Allow reprocessing without re-querying APIs
- Track ingestion timestamps and duplicate values
- Handle incremental updates
- Support modular multi-source ingestion

### Operations

```python
ingest_raw
  fetch API data
  write raw JSON/JSONL
  update duplicate values
```

### Bronze Storage

Raw responses are stored in:

```text
bronze/
```

Typical formats include:
- `.json`
- `.jsonl`

The bronze layer should remain append-only whenever possible so historical raw responses are preserved.

### Example Bronze Record

```json
{
  "source": "miso_notifications",
  "record_id": "53ef5ce06c06474ad3a88b23fca73a944c828ee736df61b68f57bd542c3df5ac",
  "content_hash": "f1ca4716c08f2d730a8a3369a190f53236ef17d89acb0b469712309cc68aee84",
  "dedupe_key": "53ef5ce06c06474ad3a88b23fca73a944c828ee736df61b68f57bd542c3df5ac:f1ca4716c08f2d730a8a3369a190f53236ef17d89acb0b469712309cc68aee84",
  "retrieved_at": "2026-05-19T17:20:29.696968+00:00",
  "run_id": "20260519T172029Z",
  "raw": {
    ...
  }
}
```

### Record Components

- `source`  
  Identifies which ingestion source produced the record.

- `record_id`  
  Stable identifier for the logical record.

- `content_hash`  
  Hash of the raw content used to detect changes in the source payload.

- `dedupe_key`  
  Combined identifier used for incremental ingestion and deduplication.

- `retrieved_at`  
  UTC timestamp indicating when the record was collected.

- `run_id`  
  Identifier for the ingestion pipeline execution.

- `raw`  
  Original unmodified source response.

## 2. Standardization (Silver Layer)

The silver layer converts heterogeneous source responses into a unified schema.

Different APIs return data in very different formats. The standardization stage ensures that all records can be processed consistently downstream.

### Goals

- Parse source-specific responses
- Normalize fields across sources
- Create a shared schema
- Perform lightweight text cleaning
- Remove malformed records
- Generate stable IDs for deduplication

### Operations

```python
standardize
  read raw
  parse records
  convert to TextRecord
  write silver CSV/Parquet
```

# Shared Text Schema

All standardized records are converted into a common `TextRecord` structure.

Example fields:

```python
TextRecord(
    record_id,
    source,
    source_type,
    title,
    text,
    published_at,
    retrieved_at,
    url,
    region,
    categories,
    raw
)
```

## Silver Storage

Standardized records are stored in:

```text
silver/
```

Formats may include:
- CSV
- Parquet

Records are partitioned by source but can also be further split by date

## Text Cleaning Strategy

Only lightweight and non-destructive preprocessing should occur in silver.

Examples:
- strip HTML
- normalize whitespace
- remove duplicated line breaks
- standardize encodings
- basic parsing cleanup

The goal is to preserve semantic meaning while improving consistency.

Recommended pattern:

```text
text_raw     -> original extracted text
text_clean   -> lightly cleaned text
```

## 3. Feature Engineering / Embeddings (Gold Layer)

The gold layer produces modeling-ready datasets.

This layer combines standardized text data with downstream feature engineering and embedding generation.

### Planned Goals

- Combine multiple text sources
- Chunk long documents
- Generate embeddings
- Create temporal aggregations
- Join with forecasting targets
- Produce model-ready datasets

### Example Operations

```python
gold_processing
  read silver data
  preprocess for embeddings
  generate embeddings
  combine sources
  aggregate features
  write gold datasets
```

## Gold Storage

Gold datasets are stored in:

```text
gold/
```

Potential formats:
- Parquet
- CSV
- vector databases
- embedding stores

Example outputs:
- embedding tables
- forecasting features
- aggregated NLP signals
- downstream ML datasets

## Incremental Updates

The ingestion framework is designed to support incremental ingestion.

Each source maintains:
- retrieval timestamps
- checkpoints
- deduplication logic
- stable record IDs

This allows the system to:
- avoid duplicate ingestion
- continue from previous runs
- support scheduled updates
- minimize API usage

## Deduplication

Stable record IDs are generated using deterministic hashing.

Example strategy:

```python
stable_hash(
    source +
    published_at +
    title +
    url
)
```

This ensures:
- identical records map to the same ID
- rerunning ingestion does not create duplicates
- records remain stable across runs



# High-Level Pipeline Flow

```text
External APIs
      |
      v
+----------------+
| Bronze Layer   |
| Raw JSON/JSONL |
+----------------+
      |
      v
+----------------+
| Silver Layer   |
| Standardized   |
| Text Records   |
+----------------+
      |
      v
+----------------+
| Gold Layer     |
| Embeddings &   |
| ML Features    |
+----------------+
```
