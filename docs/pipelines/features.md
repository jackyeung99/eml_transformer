# Feature Pipeline

The feature pipeline converts one standardized or derived dataset into a reusable Gold feature set.

```text
Silver or Gold input
    ↓
Registered feature builder
    ↓
Gold feature set
```

The pipeline handles configuration, storage, builder selection, and result reporting. The selected builder contains the actual feature-engineering logic.

## Responsibilities

The feature pipeline:

1. Receives a typed `FeatureDefinition`.
2. Checks whether the feature is enabled.
3. Reads the configured input as a DataFrame.
4. Resolves the builder from the feature registry.
5. Passes the configured options to the builder.
6. Verifies that the builder returns a DataFrame.
7. Writes the result to Gold storage.
8. Returns a `FeatureResult`.

## Configuration

A feature definition contains one input dataset.

```yaml
features:
  eia_region_hourly:
    enabled: true
    builder: eia_region_hourly
    input: silver:eia_region:records
    output: gold:eia_region_hourly:features

    settings:
      options:
        timezone: America/New_York
        load_lags:
          - 1
          - 24
          - 168
```

| Field | Description |
|---|---|
| `name` | Name of the feature definition. |
| `enabled` | Whether the feature should be built. |
| `builder` | Name of the registered builder function. |
| `input` | Logical reference for the single input dataset. |
| `output` | Logical reference for the Gold output. |
| `settings.options` | Keyword arguments passed to the builder. |

If multiple feature sets need to be combined, that operation belongs in the dataset pipeline.

## Feature Builders

The pipeline resolves the configured builder through the feature registry:

```python
build_features = get_feature_function(
    definition.builder
)
```

A builder receives one DataFrame and returns one DataFrame:

```python
def build_features(
    records: pd.DataFrame,
    *,
    timezone: str,
) -> pd.DataFrame:
    result = records.copy()

    # Validate and transform the records.

    return result
```

Builders are responsible for:

- Validating required columns
- Creating derived features
- Handling timestamps and timezones
- Defining the output grain
- Checking output keys
- Returning the completed DataFrame

Builders should not read configuration files or access storage directly.

## Input and Output Handling

The pipeline loads the complete input dataset:

```python
records = storage.read_dataset(
    definition.input
)
```

The result must be a Pandas DataFrame.

If the input is empty, the pipeline returns `skipped` without calling the builder.

After the builder runs, its result must also be a DataFrame. A nonempty result is written using the configured output reference:

```python
storage.write_dataframe(
    ref=definition.output,
    frame=features,
)
```

If the builder returns an empty DataFrame, the pipeline returns `empty` and does not write an output.

## Result Statuses

| Status | Meaning |
|---|---|
| `success` | The feature set was built and written. |
| `skipped` | The feature was disabled or its input was empty. |
| `empty` | The builder ran but returned no rows. |
| `failed` | Reading, building, validation, or writing raised an exception. |

The result reports:

- Feature name
- Status
- Records read
- Records written
- Input reference
- Output reference
- Error message, when applicable

The current result field named `source` contains the feature definition name.

## Time-Series Features

Feature builders use UTC as the canonical timestamp for storage and joins.

Local time may be derived when required for:

- Calendar features
- Market-hour interpretation
- Holiday indicators
- Daily aggregation boundaries

Daily energy features should be grouped using the relevant market timezone while retaining a consistent canonical timestamp in the output.

## Running the Pipeline

```bash
uv run eml_transformer features \
    --name eia_region_hourly \
    --config configs/dev.yaml
```

The input dataset must already exist, and the configured builder must be registered.

## Current Limitations

The pipeline currently reads and transforms the complete input dataset in memory. Future work may add incremental or partition-based feature processing.

The pipeline also reads a configured `write_mode`, but does not currently pass it to `write_dataframe()`. The setting should either be implemented or removed to avoid implying that it changes write behavior.

## Related Documentation

- [Adding a Feature](../guides/adding-a-feature.md)
- [Configuration](../guides/configuration.md)
- [Data Flow](../architecture/data-flow.md)
- [Storage Layout](../architecture/storage-layout.md)
- [Datasets](datasets.md)