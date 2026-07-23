# EML Transformer

Pipeline for ingesting and processing energy-related textual data
for NLP-driven load forecasting research.


# Overview

This project collects and standardizes textual data sources such as:

- MISO notifications
- NewsAPI articles
- National Weather Service alerts



# Quick Start

## 1. Clone the Repository

```bash
git clone https://github.com/jackyeung99/eml_transformer.git
cd eml_transformer
```

## 2. Install and Sync

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```bash
uv python install 3.10
uv sync
```

`uv sync` creates `.venv` and installs the project and development dependencies.

## 3. Optional Dependencies

```bash
# Notebooks and visualization
uv sync --group notebook

# Embeddings and PyTorch
uv sync --extra embeddings

# Both
uv sync --group notebook --extra embeddings
```

<!-- Install the Playwright browser:

```bash
uv run playwright install chromium
``` -->
---

## 4. Configure Environment Variables

Create a `.env` file in the repository root:

```env
NEWSAPI_KEY=your_key_here
```


# Running the Pipeline

List all available sources 

```bash
eml_transformer sources
```

## Ingestion

Run all sources:

```bash
uv run eml_transformer ingest --source all
```

Ingest one source:

```bash
uv run eml_transformer ingest --source miso
```

---

## Standardization

Standardize all sources:

```bash
uv run eml_transformer standardize --source all
```

Standardize a single source:

```bash
eml_transformer standardize --source newsapi
```

---

## Embeddings

Generate embeddings using NVIDIA NeMo Retriever NIM embedding models for scalable GPU-accelerated inference.

```bash
uv run eml_transformer embed \
    --model nvidia/nv-embedqa-e5-v5
```


## Backfilling Historical Data 

Some api sources archive historical data. To back fill historical data run 

```bash
uv run eml_transformer backfill   --source newsapi   --start-date 2026-04-20   --end-date 2026-05-20   --window-days 7
```

** this command is limited to data sources with supports_backfill=True and is also rate limited depending on source 

# Output Structure
The textual ingestion pipeline is built around the medallion architecture with the following data design structure 


### Bronze Layer

Raw API responses.

```text
data/bronze/source=
```

### Silver Layer

Cleaned and standardized records.

```text
data/silver/source=
```

### Gold Layer 
text embeddings 

```text 
data/gold/
```

# Documentation

Detailed documentation can be found in:

```text
docs/
```

Important guides:

- `docs/design_principles.md`
- `docs/project_structure` 
- `docs/ingestion_pipeline.md`

