# Ingestion Pipeline

The ingestion pipeline retrieves records from configured external sources and stores them in the Bronze layer.

It supports two operations:

| Operation | Purpose |
|---|---|
| Incremental ingestion | Retrieves recently available records using a checkpoint and overlapping lookback window. |
| Historical ingestion | Retrieves records over a requested historical period divided into smaller windows. |

Both operations share the same source implementations, storage interface, Bronze-writing logic, validation, and deduplication behavior.

## Responsibilities

The ingestion pipeline is responsible for:

- Loading source-specific ingestion settings
- Resolving API keys from environment variables
- Creating the registered source implementation
- Determining the requested date range
- Calling the source's `fetch_records()` method
- Validating the returned Bronze records
- Writing Bronze records through the storage interface
- Skipping records already present in deduplication state
- Updating checkpoints after successful processing
- Returning structured results to the CLI

The pipeline does not perform Silver standardization, feature engineering, or modeling.

## Pipeline Structure

```text
IngestionPipeline
├── incremental()
│   └── run_incremental_ingestion()
│       ├── resolve_incremental_start()
│       └── ingest_window()
└── historical()
    └── run_historical_ingestion()
        ├── validate_historical_source()
        ├── iter_date_windows()
        ├── ingest_window()
        └── summarize_historical_ingestion()
```

The shared `ingest_window()` function performs the actual retrieval and Bronze write for one date range.

This prevents incremental and historical ingestion from implementing separate record-fetching and storage behavior.

## Inputs and Outputs

### Input

Both operations receive a typed `SourceDefinition`.

```python
@dataclass(frozen=True, slots=True)
class SourceDefinition:
    name: str
    enabled: bool
    stages: frozenset[str]
    settings: dict[str, Any]
```

The definition provides:

- The registered source name
- Whether the source is enabled
- Its allowed pipeline stages
- Its source-specific settings

### Output

Incremental ingestion returns an `IngestionResult`.

Historical ingestion returns a `BackfillResult`.

Both result types allow the pipeline to report status and record counts without printing directly to the CLI.

### Stored Output

Retrieved records are written to the source's Bronze location:

```text
data/bronze/source={source}/records.jsonl
```

Persistent deduplication state is stored separately:

```text
data/metadata/dedupe/source={source}.json
```

Incremental checkpoints are stored under:

```text
data/metadata/checkpoints/source={source}.json
```

The same logical paths are used with local storage and Amazon S3.

## Source Creation

The pipeline creates a source from its registered name.

```text
SourceDefinition
    ↓
Resolve ingestion settings
    ↓
Resolve API keys
    ↓
Source registry
    ↓
Source implementation
```

Only the `ingestion` section of the source-specific settings is passed to the source constructor:

```python
ingestion_settings = resolve_api_keys(
    definition.settings.get("ingestion", {}),
    source_name=definition.name,
)

source = create_source(
    definition.name,
    **ingestion_settings,
)
```

This means source-specific configuration should separate ingestion settings from settings used by other stages.

Example:

```yaml
ingestion:
  api_key_env: EIA_API_KEY
  respondent: MISO
  lookback_days: 2
```

`resolve_api_keys()` replaces configured API-key environment references with their runtime values before the source is created.

Secrets should not be written directly into configuration files.

## Shared Window Ingestion

Both incremental and historical operations eventually call:

```python
ingest_window(
    source=source,
    source_name=source_name,
    storage=storage,
    paths=paths,
    from_date=from_date,
    to_date=to_date,
)
```

This function performs one complete retrieval and write operation.

```text
Date Window
    ↓
source.fetch_records()
    ↓
Bronze Record Validation
    ↓
storage.write_bronze()
    ↓
IngestionResult
```

### Fetching Records

The source receives the requested date range:

```python
records = source.fetch_records(
    from_date=from_date,
    to_date=to_date,
)
```

The current source interface returns all records as a list:

```python
list[BronzeRecord]
```

Each source is responsible for translating the date range into the parameters expected by its external API.

> **Future improvement**
>
> The current implementation loads all records for a window into memory. Future work should support iterator-based or batched retrieval so large windows can be processed without holding every Bronze record in memory simultaneously.

### Validating Bronze Records

Before writing, the ingestion logic verifies that every record has a `record_id`.

```python
validate_bronze_records(
    records,
    expected_source=source_name,
)
```

If one or more records have a missing or empty identifier, the complete window fails.

Stable identifiers are required for persistent deduplication. The same source record should receive the same identifier when it is returned by overlapping or repeated API requests.

### Writing Bronze Records

Validated records are passed to the shared storage interface:

```python
storage.write_bronze(
    bronze_key=paths.bronze_records(source_name),
    dedupe_key=paths.dedupe_state(source_name),
    records=records,
)
```

The storage layer returns counts for:

- Records received
- Records written
- Records skipped

Previously seen records are skipped using the source's persistent deduplication state.

The ingestion pipeline therefore does not need to compare new records against the entire Bronze file directly.

## Incremental Ingestion

Incremental ingestion retrieves records that may have become available since a previous successful run.

```python
pipeline.incremental(
    definition,
    to_date=None,
)
```

### Parameters

| Parameter | Description |
|---|---|
| `definition` | Typed definition for the configured source. |
| `to_date` | Optional end of the request period. The current UTC time is used when omitted. |

### Incremental Flow

```text
Read checkpoint
    ↓
Read configured lookback
    ↓
Calculate start time
    ↓
Fetch and write one window
    ↓
Write checkpoint on success
    ↓
Return IngestionResult
```

## Incremental Date Range

The end of the request period is:

```python
to_date = to_date or utc_now()
```

The start time is calculated from the checkpoint and configured lookback.

```python
from_date = resolve_incremental_start(
    checkpoint=checkpoint,
    lookback_days=lookback_days,
    to_date=to_date,
)
```

### First Run

If no checkpoint exists, the start time is calculated from the requested end:

```text
from_date = to_date - lookback_days
```

For example:

```text
to_date:       2026-08-20 12:00 UTC
lookback_days: 2
from_date:     2026-08-18 12:00 UTC
```

### Later Runs

If a checkpoint exists, the pipeline subtracts the lookback period from the previous checkpoint:

```text
from_date = previous checkpoint - lookback_days
```

For example:

```text
previous checkpoint: 2026-08-20 11:00 UTC
lookback_days:        1
from_date:            2026-08-19 11:00 UTC
```

The overlap allows the pipeline to retrieve records that were published late or revised after an earlier run.

Persistent deduplication prevents previously written records from being added again.

### Lookback Validation

`lookback_days` defaults to `1` when it is not defined:

```python
lookback_days = ingestion_settings.get(
    "lookback_days",
    1,
)
```

A negative lookback is rejected:

```text
lookback_days cannot be negative
```

A value of `0` begins the request at the previous checkpoint without adding an overlap.

## Incremental Checkpoint Behavior

The incremental checkpoint is read before the request:

```python
checkpoint_path = paths.checkpoint_key(source_name)
checkpoint = storage.read_checkpoint(checkpoint_path)
```

It is updated only when the window returns a successful result:

```python
if result.status == "success":
    storage.write_checkpoint(
        checkpoint_path,
        {
            "source": source_name,
            "last_checkpoint_value": to_date,
        },
    )
```

The checkpoint records the end of the successful request period, not the timestamp of the latest returned record.

This distinction is important because a successful API request may return no new records.

> **Checkpoint rule**
>
> The checkpoint advances only after the Bronze write completes successfully. If ingestion raises an exception, the previous checkpoint remains available for the next run.

## Incremental Result

A successful incremental run returns:

```python
IngestionResult(
    status="success",
    source=source_name,
    reason="Ingestion completed",
    from_date=from_date,
    to_date=to_date,
    records_fetched=...,
    records_written=...,
    records_skipped=...,
)
```

| Field | Meaning |
|---|---|
| `status` | Whether the operation succeeded or failed. |
| `source` | Name of the source. |
| `reason` | Short explanation of the outcome. |
| `from_date` | Beginning of the requested window. |
| `to_date` | End of the requested window. |
| `records_fetched` | Number of records received by the Bronze writer. |
| `records_written` | Number of new records written. |
| `records_skipped` | Number of records skipped by deduplication. |
| `error` | Error message when the operation fails. |

If the pipeline raises an exception, `IngestionPipeline.incremental()` catches it and returns a failure result:

```python
IngestionResult(
    status="failure",
    source=source_name,
    reason="Incremental ingestion raised an exception",
    error=str(exc),
)
```

This allows the CLI to report the failure through a structured result.

## Running Incremental Ingestion

```bash
uv run eml_transformer ingest \
    --source eia_region \
    --config configs/dev.yaml
```

The source must:

- Be enabled
- Include `ingest` in its configured stages
- Be registered
- Have valid ingestion settings

A successful run with zero written records is valid. It may mean that the API did not publish anything new or that every returned record already existed.

## Historical Ingestion

Historical ingestion retrieves a specified date range and divides it into smaller windows.

```python
pipeline.historical(
    definition,
    from_date=from_date,
    to_date=to_date,
    window_days=30,
    seed_checkpoint=False,
)
```

### Parameters

| Parameter | Description |
|---|---|
| `definition` | Typed definition for the configured source. |
| `from_date` | Beginning of the complete historical period. |
| `to_date` | End of the complete historical period. |
| `window_days` | Maximum size of each request window. Defaults to 30 days. |
| `seed_checkpoint` | Whether successful historical windows should update the incremental checkpoint. |

## Historical Source Validation

Before creating the windows, the pipeline verifies that the source supports historical retrieval.

The source must satisfy both conditions:

```python
source.update_mode == "incremental"
source.supports_backfill is True
```

A snapshot source is rejected because it does not represent an accumulating historical sequence.

A source that explicitly disables backfilling is also rejected.

The source should additionally include `backfill` in its configured stage list before the CLI allows the operation.

## Historical Date Validation

Historical ingestion requires:

- `window_days` of at least `1`
- Timezone-aware `from_date`
- Timezone-aware `to_date`
- `from_date` before or equal to `to_date`

Invalid values produce a failure result through the pipeline's exception handling.

UTC timestamps are recommended for consistency with the rest of the pipeline.

## Historical Windows

The complete range is divided into contiguous windows.

For example:

```text
Requested period: 2026-01-01 to 2026-01-20
Window size:      7 days
```

produces:

```text
Window 1: 2026-01-01 → 2026-01-08
Window 2: 2026-01-08 → 2026-01-15
Window 3: 2026-01-15 → 2026-01-20
```

The final window is shortened when fewer than `window_days` remain.

Each window is passed to the same `ingest_window()` function used by incremental ingestion.

```text
Historical range
    ↓
Date windows
    ↓
Shared ingest_window()
    ↓
Bronze storage and deduplication
```

Persistent deduplication protects against duplicated boundary records when an external API treats both ends of a date window as inclusive.

## Historical Progress

Historical ingestion displays progress using one unit per date window.

The progress display reports values such as:

- Current window
- Completed windows
- Window status
- Records fetched
- Records written
- Records skipped

Detailed ingestion logs are reduced while the progress display is active to keep console output readable.

Summary information is still logged when the backfill completes or fails.

## Failure Behavior

Results are collected after each processed window.

If a window returns a status other than `success`, the backfill stops instead of continuing to later windows.

```text
Successful window
    ↓
Successful window
    ↓
Failed window
    ↓
Stop backfill
```

The final `BackfillResult` reports the completed window and aggregated record counts.

If an exception escapes the historical ingestion helper, `IngestionPipeline.historical()` catches it and returns a failure result.

Later windows are not processed after a failure because doing so could create gaps that are difficult to identify.

## Historical Checkpoint Seeding

Historical ingestion does not update the incremental checkpoint by default:

```python
seed_checkpoint=False
```

This keeps a historical backfill independent from regular incremental ingestion.

When checkpoint seeding is enabled:

```python
seed_checkpoint=True
```

the pipeline writes the end of each successful window to the source checkpoint.

```python
{
    "source": source_name,
    "last_successful_run_id": "backfill_seed",
    "last_checkpoint_value": last_successful_window_end,
}
```

Writing after every successful window preserves the latest completed position if a later window fails.

> **Use checkpoint seeding carefully**
>
> Enable `seed_checkpoint` when a historical backfill is intended to establish the starting point for future incremental ingestion. Leave it disabled when the backfill should not affect the existing incremental schedule.

## Historical Result

Historical ingestion returns a `BackfillResult` containing:

| Field | Meaning |
|---|---|
| `status` | Overall backfill status. |
| `source` | Name of the source. |
| `from_date` | Beginning of the requested period. |
| `to_date` | End of the requested period. |
| `window_days` | Configured window size. |
| `windows_total` | Total number of generated windows. |
| `windows_completed` | Number of successful windows. |
| `records_fetched` | Total records fetched across processed windows. |
| `records_written` | Total new Bronze records written. |
| `records_skipped` | Total records skipped by deduplication. |
| `records_failed` | Number of records reported as failed, when applicable. |
| `error` | Error associated with the failed operation. |

The totals are calculated by summing the results of the individual windows.

## Running Historical Ingestion

```bash
uv run eml_transformer backfill \
    --source eia_region \
    --from-date 2026-01-01 \
    --to-date 2026-02-01 \
    --window-days 7 \
    --config configs/dev.yaml
```

Begin with a small date range to verify:

- API credentials
- Date filtering
- Pagination
- Bronze record structure
- Deduplication
- Request performance

A large historical backfill can then use a window size appropriate for the source's limits.

## Incremental and Historical Comparison

| Behavior | Incremental | Historical |
|---|---|---|
| Date range | Derived from checkpoint and lookback | Supplied explicitly |
| Number of windows | One | One or more |
| Default window size | Lookback-defined | 30 days |
| Uses persistent deduplication | Yes | Yes |
| Reads incremental checkpoint | Yes | No |
| Updates checkpoint by default | Yes | No |
| Can seed checkpoint | Not applicable | Optional |
| Stops after failure | Operation ends | Remaining windows are not processed |
| Result type | `IngestionResult` | `BackfillResult` |

## Logging

The ingestion pipeline logs:

- Source name
- Requested date range
- Created source-adapter type
- Records fetched
- Records written
- Records skipped
- Historical window progress
- Final pipeline status
- Exceptions and error details

API keys should never appear in logs. They are resolved only when constructing the source implementation.

## Operational Considerations

### Publication Timing

The pipeline retrieves whatever records are available from the external API when it runs.

A scheduled ingestion task may run before a source publishes its latest data. The overlapping lookback window allows a later run to retrieve records that were published after the earlier request.

### Deduplication

Overlapping incremental requests are intentional. Do not remove the overlap solely because it causes the API to return previously seen records.

The deduplication state prevents those records from being written repeatedly.

### Bronze File Growth

The current path helper writes source records to one logical Bronze location:

```text
data/bronze/source={source}/records.jsonl
```

As Bronze datasets grow, future work may partition them by ingestion date, source date, or run identifier.

### Memory Usage

Each source currently returns a complete list of records for a window. Large backfills should therefore use a reasonable `window_days` value.

Future iterator or batch support would reduce memory usage further.

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
```

The pipeline uses:

- `definition.name` to resolve the source implementation
- `definition.settings["ingestion"]` to construct it
- `lookback_days` to calculate the incremental start time
- The configured stage list to determine which CLI operations are permitted

## Testing Recommendations

Tests should cover:

### Incremental Ingestion

- First run without a checkpoint
- Later run with a checkpoint
- Default lookback
- Zero-day lookback
- Negative lookback rejection
- Successful checkpoint update
- Checkpoint preservation after failure
- Empty source response
- Duplicate records
- Records missing identifiers

### Historical Ingestion

- Valid window generation
- Shortened final window
- One-day windows
- Invalid window size
- Timezone-naive dates
- Reversed date range
- Unsupported snapshot source
- Source with backfill disabled
- Failure in an intermediate window
- Aggregated result counts
- Checkpoint seeding
- Backfill without checkpoint seeding

### Storage Integration

- Bronze records are written to the expected key
- Deduplication state is updated
- Repeated records are skipped
- Local and S3 storage produce equivalent logical behavior

## Related Documentation

- [Adding a Source](../guides/adding-a-source.md)
- [Configuration](../guides/configuration.md)
- [CLI Reference](../guides/cli-reference.md)
- [Data Flow](../architecture/data-flow.md)
- [Storage Layout](../architecture/storage-layout.md)
- [Standardization](standardization.md)
- [Scheduling](../operations/scheduling.md)
- [Troubleshooting](../operations/troubleshooting.md)