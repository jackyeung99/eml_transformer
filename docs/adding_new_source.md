

## Adding New Sources

New ingestion sources should inherit from `TextSource` and register themselves using the source registry.

Example:

```python
from eml_transformer.ingestion.base import TextSource
from eml_transformer.ingestion.registry import register_source


@register_source("example_source")
class ExampleSource(TextSource):

    name = "example_source"
    source_type = "api"
    update_mode = "incremental"

    def fetch_raw(
        self,
        from_date: str | None = None,
        to_date: str | None = None,
    ):
        ...

    def parse_records(self, raw):
        ...

    def standardize_record(self, record):
        ...

    def get_checkpoint_value(self, record):
        return record.get("published_at")
```

### Required Methods

| Method | Purpose |
|---|---|
| `fetch_raw()` | Pull raw data from the source |
| `parse_records()` | Extract individual records |
| `standardize_record()` | Convert records into a shared `TextRecord` schema |
| `get_checkpoint_value()` | Return the timestamp/value used for incremental updates |

### Update Modes

| Mode | Description |
|---|---|
| `"incremental"` | Source supports incremental fetching using checkpoints |
| `"snapshot"` | Source only exposes currently available data |

### Registering the Source

After adding the source file under:

```text
eml_transformer/ingestion/sources/
```

the registry will automatically discover it through:

```python
import eml_transformer.ingestion.sources
```

### Adding Source Configuration

Add the source configuration to your YAML config:

```yaml
sources:
  example_source:
    enabled: true
    api_key: ${API_KEY} # this is the reference to the key in .env
```