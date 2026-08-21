# Standardization Pipeline

The standardization pipeline converts source-specific Bronze records into shared Silver record schemas.

Each source controls how its own raw payload is interpreted. The pipeline controls iteration, error handling, batching, storage, and result reporting.

```text
Bronze JSONL records
    ↓
Reconstruct BronzeRecord
    ↓
Source standardization method
    ↓
NumericRecord or TextRecord
    ↓
Silver Parquet batches
```

## Responsibilities

The standardization pipeline is responsible for:

- Creating the registered source implementation
- Resolving the Bronze input path
- Resolving the configured Silver output
- Reading Bronze JSON Lines records
- Reconstructing each `BronzeRecord`
- Calling the source's `standardize_record()` method
- Handling records that produce zero, one, or multiple outputs
- Logging and counting record-level failures
- Writing successful records as Parquet batches
- Returning a structured result to the CLI

The source implementation is responsible for understanding its own payload and mapping it into the correct shared Silver schema.

## Inputs and Outputs

### Input

The pipeline receives:

```python
source_name: str
source_config: dict[str, Any]
```

| Input | Description |
|---|---|
| `source_name` | Registered name used to create the source implementation. |
| `source_config` | Complete source-specific configuration containing a `standardization` section. |

The Bronze input path is derived from the registered source name:

```text
data/bronze/source={source}/records.jsonl
```

### Output

The default output reference is:

```text
silver:{source}:records
```

For example:

```text
silver:eia_region:records
```

This resolves to a Silver dataset directory such as:

```text
data/silver/source=eia_region/artifact=records/
```

The standardized records are written as numbered Parquet batches:

```text
part-00000.parquet
part-00001.parquet
part-00002.parquet
```

## Pipeline Flow

```text
Source name and configuration
    ↓
Read standardization settings
    ↓
Create registered source
    ↓
Resolve Bronze and Silver locations
    ↓
Verify Bronze data exists
    ↓
Iterate through Bronze records
    ↓
Standardize each record
    ↓
Write Parquet batches
    ↓
Return StandardizationResult
```

## Source Creation

The pipeline creates the source through the shared source registry:

```python
source = create_source(
    source_name,
    **source_options,
)
```

Importing `eml_transformer.sources` ensures that registered source modules are loaded before registry lookup occurs.

The source must:

- Be registered with its configured name
- Be imported through the source package
- Implement `standardize_record()`
- Return the appropriate shared Silver record type

## Standardization Configuration

Standardization settings are stored under the source's `standardization` section.

```yaml
standardization:
  output: silver:new_source:records
  batch_size: 100000
  write_mode: replace

  options:
    example_setting: example_value
```

### Configuration Fields

| Field | Default | Description |
|---|---:|---|
| `output` | `silver:{source}:records` | Logical reference for the Silver output dataset. |
| `batch_size` | `100000` | Maximum number of output records written to each Parquet batch. |
| `write_mode` | `replace` | Determines how the Silver output is written. |
| `options` | `{}` | Source-constructor settings used during standardization. |

A minimal configuration may omit every optional field:

```yaml
standardization: {}
```

The pipeline will then use:

```text
Output:       silver:{source}:records
Batch size:   100,000
Write mode:   replace
```

## Source Options

A nested `options` mapping is the preferred format for source-constructor settings:

```yaml
standardization:
  output: silver:new_source:records
  batch_size: 100000
  write_mode: replace

  options:
    timezone: America/New_York
    variable_map:
      D: actual_load
      DF: load_forecast
```

Only the contents of `options` are passed to the source constructor.

```python
source_options = dict(
    stage_config["options"]
)
```

### Legacy Flat Configuration

The pipeline also supports the older flat configuration format:

```yaml
standardization:
  output: silver:new_source:records
  batch_size: 100000
  write_mode: replace
  timezone: America/New_York
```

When `options` is absent, the pipeline removes orchestration fields before passing the remaining values to the source:

```text
Removed:
- input
- output
- batch_size
- write_mode

Passed to source:
- all other standardization settings
```

The nested `options` format is preferred because it clearly separates pipeline behavior from source-specific settings.

## Bronze Input Validation

Before reading records, the pipeline confirms that the Bronze path exists:

```python
if not storage.exists(bronze_key):
    ...
```

If no Bronze data is available, the pipeline returns:

```text
status: skipped
records_read: 0
records_out: 0
```

The result includes the expected Bronze and Silver paths along with an explanatory message.

Missing Bronze data is treated as a skipped operation rather than an unhandled failure.

## Record Processing

The pipeline reads Bronze data one JSON Lines record at a time:

```python
for row in storage.iter_jsonl(bronze_key):
    ...
```

Each stored dictionary is reconstructed into a typed Bronze record:

```python
bronze_record = BronzeRecord.from_dict(row)
```

The source then performs its source-specific conversion:

```python
result = source.standardize_record(
    bronze_record,
)
```

The source's standardization method may return:

- One standardized record
- Multiple standardized records
- `None`

## One Bronze Record to One Silver Record

The most common behavior is one standardized output per Bronze input:

```text
One Bronze record
    ↓
standardize_record()
    ↓
One Silver record
```

For example, one EIA measurement response may become one `NumericRecord`.

## One Bronze Record to Multiple Silver Records

A source may return a list or tuple when one Bronze payload contains several logical Silver observations:

```text
One Bronze record
    ↓
standardize_record()
    ↓
Multiple Silver records
```

The pipeline handles this automatically:

```python
standardized_records = (
    result
    if isinstance(result, (list, tuple))
    else (result,)
)
```

Each returned record is converted to a dictionary and passed to the Parquet writer.

Because one Bronze record can produce multiple Silver records, `records_out` may be greater than `records_read`.

## Filtered Records

A source may return `None` when a valid Bronze record should not produce a Silver output:

```python
if result is None:
    continue
```

This can be used when:

- A record does not contain a relevant measurement
- A document does not meet source-specific requirements
- The payload represents metadata rather than an observation
- The record is intentionally filtered

Returning `None` is not counted as a standardization failure.

The current result object does not report filtered records separately.

## Standardized Record Types

Numeric sources should return `NumericRecord` objects.

Text sources should return `TextRecord` objects.

Both conform to the shared `StandardizedRecord` type expected by the pipeline.

Before writing, each output is converted through:

```python
record.to_dict()
```

The pipeline does not need to know the fields specific to numeric or text records.

The complete schemas are documented in [Schemas](../reference/schemas.md).

## Record-Level Error Handling

Each Bronze record is processed inside its own exception boundary.

If one record cannot be reconstructed or standardized:

1. `records_failed` is increased.
2. The source and Bronze row number are logged.
3. The exception is logged with its traceback.
4. Processing continues with the next Bronze record.

```text
Valid record     → Silver output
Invalid record   → Log failure and continue
Valid record     → Silver output
```

This prevents one malformed record from stopping the complete source standardization run.

### Partial Success

A run can return `status="success"` while also reporting failed records.

For example:

```text
status:          success
records_read:    100,000
records_out:      99,995
records_failed:        5
```

The status indicates that the overall read and write operation completed. `records_failed` must still be reviewed because some individual Bronze records were not standardized.

## Parquet Batching

Standardized records are yielded as an iterator to the storage writer:

```python
records_out = storage.write_records(
    ref=output_ref,
    records=records,
    batch_size=batch_size,
    mode=write_mode,
)
```

The writer groups the output into numbered Parquet batches.

```text
Silver dataset
├── part-00000.parquet
├── part-00001.parquet
└── part-00002.parquet
```

Batching provides several benefits:

- The pipeline does not need to hold every Silver record in memory.
- Large datasets are divided into manageable files.
- Local and S3 storage use the same logical behavior.
- Readers can treat all part files as one dataset.

The configured `batch_size` applies to Silver output records, not Bronze input rows.

Because one Bronze record may produce multiple Silver records, the number of Bronze rows represented by one Parquet batch can vary.

## Write Modes

The default write mode is:

```yaml
write_mode: replace
```

With replacement mode, the current Silver dataset is rebuilt from the available Bronze input.

Other write modes may be supported by the storage implementation, but they should be used carefully.

> **Important**
>
> The current standardization pipeline reads the complete Bronze source on every run. Using an append mode without incremental input tracking could append previously standardized records again.

Until incremental standardization is implemented, `replace` is the safest default for rebuilding a Silver dataset from the complete Bronze source.

## Standardization Result

The pipeline returns a `StandardizationResult`.

```python
@dataclass(slots=True)
class StandardizationResult:
    status: str
    source: str

    records_read: int
    records_out: int
    records_failed: int = 0

    bronze_key: str | None = None
    silver_key: str | None = None

    error: str | None = None
```

### Result Fields

| Field | Description |
|---|---|
| `status` | `success`, `skipped`, or `failure`. |
| `source` | Registered source name. |
| `records_read` | Number of Bronze rows read. |
| `records_out` | Number of Silver records written. |
| `records_failed` | Number of Bronze rows that raised record-level errors. |
| `bronze_key` | Resolved Bronze input path. |
| `silver_key` | Resolved Silver output path. |
| `error` | Skip reason or pipeline-level error message. |

The result provides a summary mapping for CLI or workflow output:

```python
result.to_summary()
```

Example:

```python
{
    "source": "eia_region",
    "status": "success",
    "read": 100000,
    "out": 99995,
    "failed": 5,
    "bronze": "data/bronze/source=eia_region/records.jsonl",
    "silver": "data/silver/source=eia_region/artifact=records",
    "error": None,
}
```

## Pipeline-Level Failure Handling

Exceptions outside individual record conversion are treated as pipeline failures.

Examples include:

- Invalid source configuration
- Unregistered source name
- Invalid output reference
- Bronze read failure
- Parquet write failure
- Storage connection failure

The pipeline catches the exception, logs the traceback, and returns:

```text
status: failure
records_out: 0
error: <exception message>
```

The result also preserves the number of Bronze rows read and record-level failures observed before the pipeline stopped.

## Status Meanings

| Status | Meaning |
|---|---|
| `success` | Bronze data was processed and the Silver write completed. Individual record failures may still be present. |
| `skipped` | No Bronze input existed for the source. |
| `failure` | A pipeline-level exception prevented completion. |

## Logging

The pipeline logs:

- Source name
- Resolved Bronze path
- Resolved Silver path
- Batch size
- Write mode
- Records read
- Records written
- Record-level failures
- Elapsed time
- Pipeline-level exceptions

Each record-level exception includes the source name and Bronze row number.

The active implementation logs the final totals but does not currently emit periodic throughput reports during processing.

## Running Standardization

Run standardization for one source:

```bash
uv run eml_transformer standardize \
    --source eia_region \
    --config configs/dev.yaml
```

The source must:

- Be enabled
- Include `standardize` in its configured stages
- Be registered and imported
- Have Bronze data available
- Provide a working `standardize_record()` implementation

## Configuration Example

Main configuration:

```yaml
sources:
  eia_region:
    enabled: true
    config: sources/eia_region.yaml

    stages:
      - ingest
      - backfill
      - standardize
```

Source-specific configuration:

```yaml
ingestion:
  api_key_env: EIA_API_KEY
  respondent: MISO
  lookback_days: 2

standardization:
  output: silver:eia_region:records
  batch_size: 100000
  write_mode: replace

  options:
    respondent: MISO
```

The `ingestion` and `standardization` sections have separate responsibilities.

| Section | Used for |
|---|---|
| `ingestion` | Constructing the source for external data retrieval |
| `standardization` | Constructing the source for Bronze-to-Silver conversion and configuring the Silver write |

## Current Limitation: Full-History Processing

The current pipeline standardizes the complete Bronze JSON Lines file during every run.

```text
Complete Bronze source
    ↓
Standardize every record
    ↓
Replace complete Silver dataset
```

This is simple and reliable for smaller datasets, but becomes inefficient as historical data grows.

Repeated runs may:

- Reread records that were already standardized
- Repeat source-specific transformations
- Rewrite unchanged Silver batches
- Transfer large Bronze files from S3
- Increase runtime and compute cost

> **Future improvement**
>
> Standardization should support separate historical and incremental modes. Incremental standardization should process only Bronze batches or records added since the last successful standardization run.
>
> This will require tracking the standardized Bronze position or batch identity, writing only new Silver batches, and advancing a standardization checkpoint only after a successful write.
>
> Until this work is complete, the standardization stage should generally use `write_mode: replace` to avoid duplicating previously processed Silver records.

## Future Bronze Partitioning

The current Bronze layout stores a source under one logical JSON Lines path:

```text
data/bronze/source={source}/records.jsonl
```

Partitioning Bronze records by ingestion date, run identifier, or batch would make incremental standardization easier.

A future layout could identify which Bronze batches have already been converted without rereading the complete source history.

Any change should preserve the shared storage interface so the same logic works locally and in Amazon S3.

## Testing Recommendations

Tests should cover the following behavior.

### Configuration

- Default output reference
- Custom output reference
- Default batch size
- Custom batch size
- Default write mode
- Nested `options`
- Legacy flat source options
- Removal of orchestration settings

### Input Handling

- Bronze input exists
- Bronze input is missing
- Empty Bronze file
- Valid `BronzeRecord` reconstruction
- Invalid Bronze dictionaries

### Source Results

- One Silver record returned
- Multiple Silver records returned
- `None` returned
- Numeric records
- Text records
- Record conversion failure

### Failure Handling

- One invalid record does not stop later records
- Failed records are counted
- Overall write failures return `failure`
- Missing Bronze data returns `skipped`
- Successful runs may report nonzero record failures

### Storage

- Correct Bronze path is used
- Correct Silver reference is used
- Records are written in configured batches
- Replacement mode rebuilds the output
- Local and S3 backends follow the same logical behavior

## Related Documentation

- [Adding a Source](../guides/adding-a-source.md)
- [Configuration](../guides/configuration.md)
- [CLI Reference](../guides/cli-reference.md)
- [Schemas](../reference/schemas.md)
- [Data Flow](../architecture/data-flow.md)
- [Storage Layout](../architecture/storage-layout.md)
- [Ingestion](ingestion.md)
- [Features](features.md)
- [Troubleshooting](../operations/troubleshooting.md)