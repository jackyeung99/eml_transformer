# Embedding Pipeline

The embedding pipeline converts standardized or enriched text records into vector embeddings stored in the Gold layer.

```text
Silver text records
    ↓
Build embedding text
    ↓
Sentence-transformer model
    ↓
Gold embedding batches
```

The pipeline processes input and output in batches so the complete dataset does not need to be loaded into one DataFrame.

## Responsibilities

The embedding pipeline:

1. Reads embedding configuration.
2. Resolves the input and output dataset references.
3. Checks that the input exists.
4. Loads an embedding model.
5. Reads text records in batches.
6. Combines the configured text columns.
7. Skips invalid or previously embedded records.
8. Generates embeddings.
9. Writes Gold output batches.
10. Returns an `EmbeddingResult`.

## Configuration

An embedding configuration may contain:

```yaml
embeddings:
  miso_notifications:
    model: nvidia/llama-nemotron-embed-vl-1b-v2
    input: silver:miso_notifications:records
    output: gold:miso_notifications:embeddings

    input_type: passage
    text_columns:
      - title
      - text

    embedding_batch_size: 32
    write_mode: append
    device: null
```

| Field | Default | Description |
|---|---|---|
| `model` | `nvidia/llama-nemotron-embed-vl-1b-v2` | Sentence-transformer model to load. |
| `input` | `silver:{source}:records` | Dataset containing text records. |
| `output` | `gold:{source}:embeddings` | Gold embedding output. |
| `input_type` | `passage` | Input type recorded with each embedding. |
| `text_columns` | `["title", "text"]` | Columns combined into the embedding text. |
| `embedding_batch_size` | `32` | Number of texts sent to the model at once. |
| `write_mode` | `append` | How output batches are written. |
| `device` | Model default | Device used by the embedding model. |

The embedding dependencies must be installed:

```bash
uv sync --extra embeddings
```

## Input Handling

The pipeline checks that the configured input path exists.

If it does not exist, the pipeline returns:

```text
status: skipped
error: No embedding input found
```

Input records are then read in batches:

```python
for frame in storage.read_batches(input_ref):
    ...
```

Each batch must contain a `record_id` column. A missing `record_id` causes that batch to fail.

## Building the Embedding Text

The configured text columns are combined for each record.

```yaml
text_columns:
  - title
  - text
```

Nonempty values are normalized and joined with a blank line:

```text
Document title

Document body
```

Missing values and empty strings are ignored.

If every configured text field is missing or empty, the record is skipped.

## Deduplication

Records are deduplicated using `record_id`.

Within each input batch, duplicate identifiers are reduced to the last occurrence:

```python
frame.drop_duplicates(
    subset=["record_id"],
    keep="last",
)
```

When `write_mode` is `append`, the pipeline first reads existing embedding batches and collects their record identifiers.

Records already present in the Gold output are skipped rather than embedded again.

```text
Input record ID
    ↓
Already in output?
   ↙             ↘
 Yes             No
 Skip          Embed
```

Newly created identifiers are added to the in-memory set so duplicates in later input batches are also skipped.

## Embedding Generation

The pipeline creates a `SentenceTransformerEmbedder` unless an embedder was supplied when the pipeline was constructed.

```python
client = SentenceTransformerEmbedder(
    model_name=model_name,
    device=device,
)
```

Selected text is sent to the model using the configured batch size:

```python
embeddings = client.embed(
    output["embedding_text"].tolist(),
    batch_size=embedding_batch_size,
)
```

The output retains the selected input fields and adds:

| Column | Description |
|---|---|
| `embedding_text` | Combined text sent to the model. |
| `embedding` | Generated numeric vector. |
| `embedding_model` | Name of the model used. |
| `embedding_input_type` | Configured input type. |
| `source` | Source associated with the record. |

## Batch Failure Handling

Each input DataFrame is processed inside its own exception boundary.

If a batch fails:

- Every row in the batch is counted as failed.
- The exception is logged.
- The batch is not written.
- Processing continues with the next batch.

This prevents one invalid batch from stopping the complete embedding run.

## Writing Embeddings

Nonempty output batches are written through:

```python
storage.write_batches(
    ref=output_ref,
    batches=output_batches,
    mode=write_mode,
)
```

The default mode is `append`, allowing later runs to add embeddings for newly available records.

```text
data/gold/embeddings/dataset={source}/
├── part-00000.parquet
├── part-00001.parquet
└── part-00002.parquet
```

## Result Statuses

| Status | Meaning |
|---|---|
| `success` | At least one new embedding was created. |
| `skipped` | The configured input dataset does not exist. |
| `empty` | The input exists but contains no records. |
| `up_to_date` | Records were read, but no new embeddings were created. |
| `failed` | A pipeline-level exception prevented completion. |

`up_to_date` may mean that every record was already embedded or that the remaining records contained no valid text.

## Embedding Result

The pipeline returns an `EmbeddingResult` containing:

- Source name
- Status
- Model name
- Records read
- Embeddings created
- Embeddings skipped
- Records failed
- Input path
- Output path
- Error message

A run may return `success` while reporting failed batches. The failure count should therefore still be reviewed.

## Running the Pipeline

```bash
uv run eml_transformer embed \
    --source miso_notifications \
    --config configs/dev.yaml
```

Before running, confirm that:

- The source includes `embed` in its configured stages
- The input Silver or enriched dataset exists
- Records contain `record_id`
- At least one configured text column exists
- Embedding dependencies are installed
- The machine has sufficient memory for the selected model

## Current Limitations

When using append mode, all existing output record identifiers are loaded into an in-memory set. This may become expensive as the embedding dataset grows.

Future improvements may include:

- Persistent embedding checkpoints
- Partition-aware processing
- Indexed deduplication state
- Row-level recovery within failed batches
- Separate statuses for invalid text and already embedded records

The configured `input_type` is currently stored as output metadata. The pipeline should verify that it is also applied by the embedding model when a model requires different query and passage encoding behavior.

## Related Documentation

- [Data Flow](../architecture/data-flow.md)
- [Storage Layout](../architecture/storage-layout.md)
- [Configuration](../guides/configuration.md)
- [Adding a Source](../guides/adding-a-source.md)
- [Standardization](standardization.md)
- [Troubleshooting](../operations/troubleshooting.md)