# Adding a Data Source

This guide explains how to add a new numeric or text source to the EML Energy Forecasting Pipeline.

Adding a source involves four steps:

1. Define how the source retrieves and standardizes records.
2. Add and register the source implementation.
3. Add the source configuration and allowed stages.
4. Verify and run the source through the CLI.

## 1. Define the Source

Every source extends the shared `DataSource` interface.

```python
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Iterable

from eml_transformer.schema.records import (
    BronzeRecord,
    StandardizedRecord,
)


class DataSource(ABC):
    name: str
    source_type: str
    update_mode: str
    supports_backfill: bool

    @abstractmethod
    def fetch_records(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Iterable[BronzeRecord]:
        ...

    @abstractmethod
    def standardize_record(
        self,
        record: dict[str, Any],
    ) -> StandardizedRecord:
        ...
```

A source implementation defines its identity, retrieval behavior, and conversion into the shared record schemas.

### Source Attributes

Each source must define the following attributes:

| Attribute | Description |
|---|---|
| `name` | Stable and unique name used in configuration, storage paths, checkpoints, and CLI commands. |
| `source_type` | Type of data produced by the source: `"numeric"` or `"text"`. |
| `update_mode` | How the external source provides updates: `"incremental"` or `"snapshot"`. |
| `supports_backfill` | Whether the source can retrieve records for a requested historical period. |

Example:

```python
class NewSource(DataSource):
    name = "new_source"
    source_type = "numeric"
    update_mode = "incremental"
    supports_backfill = True
```

#### `name`

The source name identifies the source throughout the system.

```text
Configuration:       new_source
CLI argument:        --source new_source
Dataset reference:   bronze:new_source:records
Storage directory:   source=new_source/
Checkpoint:          source=new_source.json
```

Choose a short, descriptive name and avoid changing it after the source has been used. Changing the name may cause the pipeline to create new storage paths and checkpoints.

#### `source_type`

The source type determines which kind of standardized Silver record the source produces.

```python
source_type = "numeric"
```

Numeric sources produce standardized numeric observations.

```python
source_type = "text"
```

Text sources produce standardized text documents.

#### `update_mode`

The update mode describes how new information becomes available.

```python
update_mode = "incremental"
```

An incremental source adds new records over time. The pipeline uses checkpoints and lookback windows to retrieve newly available records.

```python
update_mode = "snapshot"
```

A snapshot source returns its current state. Repeated requests may return updated versions of the same information rather than a historical sequence of records.

#### `supports_backfill`

This attribute indicates whether the source supports historical date ranges.

```python
supports_backfill = True
```

When enabled, `fetch_records()` must use the provided `start` and `end` values to retrieve historical records.

```python
supports_backfill = False
```

When disabled, the source can be used for incremental ingestion but cannot be selected for a historical backfill.

## Bronze Records

The current source interface retrieves records into a list and returns them after the request completes through the method `fetch_records()`

```python
def fetch_records(
    self,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[BronzeRecord]:
    records: list[BronzeRecord] = []

    for payload in self.client.iter_records(
        start=start,
        end=end,
    ):
        records.append(
            BronzeRecord(
                record_id=self._record_id(payload),
                source=self.name,
                retrieved_at=utc_now(),
                raw=payload,
            )
        )

    return self._deduplicate_records(records)
```

This method may:

- Send API requests
- Handle authentication
- Follow pagination
- Apply retry behavior
- Parse source responses
- Generate stable record identifiers
- Return deduplicated Bronze records

The `start` and `end` values define the requested time range. The source implementation is responsible for translating these values into the parameters required by its external API.

> **Future improvement**
>
> The current implementation collects records in memory before returning them. Future work should convert `fetch_records()` and deduplication to iterator-based processing so large historical requests can be streamed or processed in batches without loading every record into memory at once.

### Stable Record Identifiers

Every Bronze record must have a stable identifier.

The identifier should remain the same when the source returns the same record during a later request.

It may be based on:

- An identifier provided by the API
- A document URL
- A combination of observation fields
- A stable hash of identifying values

Do not base record identity on the retrieval time because it changes every time the record is requested.

Stable identifiers allow the pipeline to use overlapping request windows while preventing duplicate records.

## Silver Records

The `standardize_record()` method converts one raw Bronze payload into a shared Silver record.

```python
def standardize_record(
    self,
    record: dict[str, Any],
) -> StandardizedRecord:
    ...
```

Silver records normalize source-specific responses into common structures used by downstream stages.

A numeric source returns a numeric Silver record containing information such as:

- Observation time
- Measurement name
- Numeric value
- Unit
- Region
- Additional dimensions
- Source metadata

A text source returns a text Silver record containing information such as:

- Title
- Document text
- Publication time
- Retrieval time
- URL
- Region
- Categories
- Source metadata

Example numeric standardization:

```python
def standardize_record(
    self,
    record: dict[str, Any],
) -> StandardizedRecord:
    return NumericRecord(
        record_id=str(record["id"]),
        source=self.name,
        observed_at=parse_timestamp(record["period"]),
        retrieved_at=parse_timestamp(record["retrieved_at"]),
        measurement=record["measurement"],
        value=float(record["value"]),
        unit=record.get("unit"),
    )
```

The source handles field mapping and source-specific parsing. The standardization pipeline handles iteration, logging, error counts, and writing the completed Silver records.

The exact Bronze, numeric Silver, and text Silver fields are documented in [Schemas](../reference/schemas.md).

## Deduplication

The base source provides a helper for removing duplicate records from one retrieved collection.

```python
@staticmethod
def _deduplicate_records(
    records: list[BronzeRecord],
) -> list[BronzeRecord]:
    ...
```

Records are considered duplicates when they share the same:

```text
(source, record_id)
```

This handles duplicates caused by overlapping pages, repeated API responses, or adjacent historical windows.

The helper performs in-memory deduplication within the current collection. Persistent deduplication across separate pipeline runs is handled through stored pipeline state.

## 2. Add and Register the Source

### Choose the Source Location

Place the implementation under either `numeric/` or `text/`.

```text
src/eml_transformer/ingestion/sources/
├── numeric/
├── text/
├── base.py
└── registry.py
```

Use:

- `numeric/` for numeric time-series observations
- `text/` for documents, notifications, alerts, and articles

### Single-File Source

Use one file when the source has a small implementation or one primary endpoint.

```text
sources/
└── numeric/
    ├── __init__.py
    └── new_source.py
```

The file may contain:

- The source class
- Request logic
- Response parsing
- Small source-specific helpers

### Multi-File Source Package

Use a package when one API contains several related endpoints or requires shared client and parsing logic.

```text
sources/
└── numeric/
    └── new_api/
        ├── __init__.py
        ├── client.py
        ├── parsing.py
        ├── endpoint_a.py
        └── endpoint_b.py
```

| File | Responsibility |
|---|---|
| `client.py` | Shared authentication, requests, pagination, retries, and rate limiting |
| `parsing.py` | Shared response parsing and conversion helpers |
| `endpoint_a.py` | Source implementation for one API endpoint |
| `endpoint_b.py` | Source implementation for another API endpoint |
| `__init__.py` | Imports and exposes the registered source implementations |

For example, EIA-930 uses shared client and parsing modules while keeping regional and interchange sources separate.

```text
sources/numeric/eia930/
├── __init__.py
├── client.py
├── parsing.py
├── region.py
└── interchange.py
```

Use shared helpers when several endpoints require the same authentication, pagination, or parsing behavior. Do not duplicate an API client for each endpoint.

## Register the Source

Apply the `@register_source` decorator to the source class.

```python
from eml_transformer.ingestion.sources.base import DataSource
from eml_transformer.ingestion.sources.registry import (
    register_source,
)


@register_source
class NewSource(DataSource):
    name = "new_source"
    source_type = "numeric"
    update_mode = "incremental"
    supports_backfill = True

    ...
```

The decorator automatically adds the class to the source registry when Python imports the module.

```text
Import module
    ↓
Evaluate source class
    ↓
Run @register_source
    ↓
Add source to registry
```

The registered name comes from the source's `name` attribute.

You do not need to edit a registry dictionary manually when using the decorator.

## Update the Package Imports

The decorator runs only when the source module is imported. After adding a source, manually update the appropriate `__init__.py`.

For a single-file numeric source:

```python
# src/eml_transformer/ingestion/sources/numeric/__init__.py

from eml_transformer.ingestion.sources.numeric.new_source import (
    NewSource,
)
```

For a single-file text source:

```python
# src/eml_transformer/ingestion/sources/text/__init__.py

from eml_transformer.ingestion.sources.text.new_source import (
    NewSource,
)
```

For a multi-file source package, import the registered sources in the package initializer:

```python
# src/eml_transformer/ingestion/sources/numeric/new_api/__init__.py

from eml_transformer.ingestion.sources.numeric.new_api.endpoint_a import (
    EndpointASource,
)
from eml_transformer.ingestion.sources.numeric.new_api.endpoint_b import (
    EndpointBSource,
)
```

Then import them through the parent package:

```python
# src/eml_transformer/ingestion/sources/numeric/__init__.py

from eml_transformer.ingestion.sources.numeric.new_api import (
    EndpointASource,
    EndpointBSource,
)
```

> **Important**
>
> A source is not registered merely because its file exists or because it uses `@register_source`. Its module must also be imported through the package initialization path.
## 3. Add the Configuration

Source configuration is divided between:

1. The main environment configuration
2. A source-specific configuration file under `configs/sources/`

```text
configs/
├── dev.yaml
├── prod.yaml
└── sources/
    ├── eia_region.yaml
    ├── eia_interchange.yaml
    └── miso_notifications.yaml
```

The main configuration enables the source and identifies the stages in which it participates. The source-specific file contains the settings passed to the source implementation.

## Add the Source to the Main Configuration

Add the source under `sources` in the appropriate environment configuration.

```yaml
sources:
  new_source:
    enabled: true
    config: sources/new_source.yaml

    stages:
      - ingest
      - backfill
      - standardize
```

The configuration key must match the name declared by the registered source:

```text
Registered source name:    new_source
Main configuration key:    new_source
```

The `config` field points to the source-specific YAML file relative to the main `configs/` directory:

```text
config: sources/new_source.yaml
        ↓
configs/sources/new_source.yaml
```

### Main Source Fields

| Field | Description |
|---|---|
| `enabled` | Determines whether the source is available to workflows and CLI operations. |
| `config` | Path to the source-specific configuration file. |
| `stages` | Lists the processing stages in which the source participates. |

This separation keeps the main environment configuration concise while allowing each source to maintain its own settings.

## Create the Source-Specific Configuration

Create a YAML file under `configs/sources/`.

```text
configs/sources/new_source.yaml
```

Add the settings required by the source implementation:

```yaml
api_key_env: NEW_SOURCE_API_KEY
lookback_days: 2
region: example_region
page_size: 5000
```

Source-specific settings may include:

- API-key environment variables
- Endpoint parameters
- Regions or respondents
- Product or measurement types
- Request limits
- Lookback periods
- Retry settings
- Variable mappings
- Source-specific filters

For example:

```yaml
api_key_env: EIA_API_KEY
respondent: MISO

measurement_types:
  - D
  - DF
  - NG
  - TI

variable_map:
  D: actual_load
  DF: load_forecast
  NG: net_generation
  TI: total_interchange
```

These values are loaded and passed to the source implementation when the source is created.

Do not place API keys directly in the YAML file. Store the environment-variable name in `api_key_env` and provide the actual secret through the runtime environment.

## Declare the Allowed Stages

The `stages` field in the main configuration determines which operations are valid for the source.

```yaml
sources:
  new_source:
    enabled: true
    config: sources/new_source.yaml

    stages:
      - ingest
      - backfill
      - standardize
```

Declare only the stages that the source supports.

| Stage | Use |
|---|---|
| `ingest` | Retrieves recently available records and writes Bronze data. |
| `backfill` | Retrieves records over a requested historical period. |
| `standardize` | Converts Bronze payloads into shared Silver records. |
| `scrape` | Retrieves or enriches full text after standardization. |
| `embed` | Converts standardized or enriched text into Gold embeddings. |

### Numeric Source

A numeric source that supports historical retrieval commonly uses:

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

Do not add `backfill` when the source does not support historical date ranges.

The configured stages should agree with the source class:

```python
supports_backfill = True
```

### Text Source with Embeddings

A text source that already provides complete text may use:

```yaml
sources:
  miso_notifications:
    enabled: true
    config: sources/miso_notifications.yaml

    stages:
      - ingest
      - standardize
      - embed
```

### Text Source Requiring Scraping

A text source that initially provides only metadata or article URLs may use:

```yaml
sources:
  gdelt:
    enabled: true
    config: sources/gdelt.yaml

    stages:
      - ingest
      - backfill
      - standardize
      - scrape
      - embed
```

The `scrape` stage enriches the standardized records before embedding.

Do not add `scrape` when:

- The source already provides complete text
- Records do not contain retrievable URLs
- No scraper implementation exists for the source

Do not add `embed` to numeric sources or text sources that are not intended to produce embeddings.

## Configuration Example

The resulting configuration is split across two files.

Main environment configuration:

```yaml
# configs/dev.yaml

sources:
  new_source:
    enabled: true
    config: sources/new_source.yaml

    stages:
      - ingest
      - backfill
      - standardize
```

Source-specific setting configuration:

```yaml
# configs/sources/new_source.yaml

api_key_env: NEW_SOURCE_API_KEY
lookback_days: 2
region: example_region
page_size: 5000
```

The main configuration answers:

```text
Is the source enabled?
Which stages can run?
Where are its settings?
```

The source-specific configuration answers:

```text
How should this source connect and behave?
```



## 4. Verify and Run the Source

### Verify Registration

Use the inspection command to confirm that the source is registered and available.

```bash
uv run eml_transformer inspect sources \
    --config configs/dev.yaml
```

Confirm that the source name appears in the output with the expected status and stages.

If the source is missing, verify that:

1. The class uses `@register_source`.
2. The source declares a unique `name`.
3. The configuration key matches the source name.
4. The source module is imported in its local `__init__.py`.
5. The source package is imported by its parent `__init__.py`.
6. The source is enabled in the selected configuration.

### Run Incremental Ingestion

Retrieve the records currently available from the source:

```bash
uv run eml_transformer ingest \
    --source new_source \
    --config configs/dev.yaml
```

Inspect the Bronze output and confirm:

- Records were retrieved
- Record identifiers are stable
- Raw payloads are preserved
- Retrieval timestamps are valid
- Duplicate records were not introduced

### Run Historical Backfill

If `supports_backfill` is `True`, test a small historical period:

```bash
uv run eml_transformer backfill \
    --source new_source \
    --from-date 2026-01-01 \
    --to-date 2026-01-08 \
    --window-days 1 \
    --config configs/dev.yaml
```

Begin with a small date range before starting a complete historical backfill.

### Run Standardization

Convert the Bronze records into Silver records:

```bash
uv run eml_transformer standardize \
    --source new_source \
    --config configs/dev.yaml
```

Inspect the Silver output and confirm:

- The correct shared schema was used
- Timestamps were parsed correctly
- Numeric values or text fields are valid
- Important source fields were preserved
- Dimensions and metadata contain expected values
- Failed records were reported clearly

### Test the Complete Workflow

After verifying each stage independently, run the workflow that includes the new source.

Confirm that the source participates only in the stages declared in its configuration.

## Final Checklist

### Source Definition

- [ ] Choose a stable source name
- [ ] Set `source_type`
- [ ] Set `update_mode`
- [ ] Set `supports_backfill`
- [ ] Implement `fetch_records()`
- [ ] Implement `standardize_record()`
- [ ] Produce stable Bronze record identifiers
- [ ] Return the correct Silver record type

### Registration

- [ ] Place the source under `numeric/` or `text/`
- [ ] Use a package if several endpoints share helpers
- [ ] Apply `@register_source`
- [ ] Update the source package `__init__.py`
- [ ] Update the parent package import when required

### Configuration

- [ ] Add the source to the YAML configuration
- [ ] Match the configuration key to the registered name
- [ ] Enable only the supported stages
- [ ] Reference secrets through environment variables

### Verification

- [ ] Verify the source through the CLI
- [ ] Run incremental ingestion
- [ ] Test historical backfill when supported
- [ ] Run standardization
- [ ] Inspect Bronze and Silver outputs
- [ ] Run the applicable workflow

## Related Documentation

- [Schemas](../reference/schemas.md) — Exact Bronze and Silver record fields
- [Configuration](configuration.md) — Source configuration behavior
- [Data Flow](../architecture/data-flow.md) — Movement from external sources to forecasts
- [Project Structure](../architecture/project-structure.md) — Source package organization
- [Storage Layout](../architecture/storage-layout.md) — Bronze and Silver storage paths
- [Ingestion](../pipelines/ingestion.md) — Incremental and historical retrieval
- [Standardization](../pipelines/standardization.md) — Bronze-to-Silver conversion