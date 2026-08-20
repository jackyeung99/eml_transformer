# Adding a Feature

This guide explains how to add a new feature set to the pipeline.

A feature builder reads one standardized or derived dataset and returns a reusable Gold feature set. The feature pipeline handles configuration, input loading, storage, and result reporting.

## 1. Define the Feature Set

Before creating a builder, define:

- The input dataset
- The fields required from the input
- The output grain
- The grouping keys
- The timestamp convention
- The features being created
- The output dataset reference

Examples of output grains include:

- One row per hour and region
- One row per Eastern calendar day and region
- One row per document
- One embedding vector per document

A feature set should represent a reusable group of related variables rather than a table designed for only one model.

If multiple feature sets must be combined, perform that operation in a dataset builder rather than a feature builder.

## 2. Create Reusable Transformations

Place small, reusable feature operations in the transformations package.

```text
src/eml_transformer/features/transformations/
```

Examples include:

- Calendar features
- Lagged values
- Rolling statistics
- Timezone conversion
- Daily aggregation
- Numeric validation

A transformation should generally accept a DataFrame and return a DataFrame without reading configuration or accessing storage.

Example:

```python
import pandas as pd


def add_example_feature(
    data: pd.DataFrame,
) -> pd.DataFrame:
    result = data.copy()
    result["example_feature"] = result["value"] * 2

    return result
```

Transformations can then be reused by multiple feature builders.

## 3. Create the Feature Builder

Add the builder to the appropriate feature module.

```text
src/eml_transformer/features/
```

A feature builder receives one input DataFrame and any configured settings.

```python
import pandas as pd


def build_new_features(
    data: pd.DataFrame,
    *,
    timestamp_column: str = "observed_at",
) -> pd.DataFrame:
    if timestamp_column not in data.columns:
        raise ValueError(
            f"Missing timestamp column {timestamp_column!r}"
        )

    result = data.copy()

    # Apply feature transformations here.

    return result
```

The builder should:

1. Validate the required input columns.
2. Copy the input before modifying it when appropriate.
3. Apply the required transformations.
4. Validate the output grain and keys.
5. Return the completed DataFrame.

The builder should not:

- Read configuration files
- Load data from storage
- Construct local or S3 paths
- Write its output
- Format CLI results

The feature pipeline handles those responsibilities.

## 4. Handle Time Correctly

Use UTC as the canonical timestamp for storage and dataset joins.

Local time should be derived only when required for:

- Calendar variables
- Local hourly interpretation
- Daily aggregation boundaries
- Other market-specific time behavior

For example, daily energy features may need to be grouped using Eastern calendar days rather than UTC calendar days.

A typical process is:

1. Convert `observed_at` from UTC to Eastern time.
2. Perform the local calendar transformation or aggregation.
3. Preserve a canonical UTC timestamp in the output.

Feature builders should document what an aggregated timestamp represents so downstream datasets and models interpret it correctly.

## 5. Register the Builder

Add the builder to the feature registry.

```python
from eml_transformer.features.new_features import (
    build_new_features,
)


FEATURE_BUILDERS = {
    "new_feature_builder": build_new_features,
}
```

The registry maps the builder name used in configuration to its Python function.

```text
Configuration name
    ↓
Feature registry
    ↓
Builder function
```

Choose a descriptive and stable registry name.

For example:

```text
eia_region_hourly
eia_region_daily
eia_interchange_hourly
eia_interchange_daily
```

## 6. Add the Feature Definition

Add the feature definition to the appropriate configuration file.

```yaml
features:
  new_features:
    enabled: true
    builder: new_feature_builder
    input: silver:new_source:records
    output: gold:new_features:features

    settings:
      timestamp_column: observed_at
```

### Configuration Fields

| Field | Description |
|---|---|
| `enabled` | Determines whether the feature definition is available to the pipeline. |
| `builder` | Name used to resolve the builder from the feature registry. |
| `input` | Logical reference for the single input dataset. |
| `output` | Logical reference for the completed Gold feature set. |
| `settings` | Optional keyword arguments passed to the builder. |

The feature pipeline resolves:

```yaml
input: silver:new_source:records
```

and passes the resulting DataFrame directly to the builder:

```python
result = build_new_features(
    data,
    timestamp_column="observed_at",
)
```

The builder does not need to know the dataset reference or storage backend.

## 7. Choose the Dataset References

The input may reference a Silver dataset:

```yaml
input: silver:eia_region:records
```

or another derived dataset when appropriate:

```yaml
input: gold:existing_features:features
```

The output should normally reference a Gold feature set:

```yaml
output: gold:new_features:features
```

A complete definition may look like this:

```yaml
features:
  eia_region_hourly:
    enabled: true
    builder: eia_region_hourly
    input: silver:eia_region:records
    output: gold:eia_region_hourly:features

    settings:
      timezone: America/New_York
      load_lags:
        - 1
        - 24
        - 168
```

## 8. Validate the Output

Feature builders should validate important assumptions before returning their output.

Validation may include:

- Required columns exist
- Timestamps are valid
- Numeric fields have appropriate types
- Output keys are not unexpectedly duplicated
- Aggregated rows have the intended grain
- Lagged values are calculated within the correct groups
- Rows are correctly ordered
- Required output columns were created

For example:

```python
required_columns = {
    "observed_at",
    "region",
    "actual_load",
}

missing = required_columns.difference(data.columns)

if missing:
    raise ValueError(
        f"Missing required columns: {sorted(missing)}"
    )
```

Errors should identify the missing field or violated assumption clearly.

## 9. Test the Feature Builder

Feature tests should use small, deterministic DataFrames with known expected outputs.

Tests should cover applicable behavior such as:

- Expected feature values
- Missing required columns
- Multiple regions or groups
- Unsorted input data
- Missing observations
- Invalid timestamps
- Timezone conversion
- Daylight-saving-time transitions
- Lag boundaries
- Rolling-window boundaries
- Daily aggregation boundaries
- Duplicate output keys

Test the builder directly without running storage or the complete pipeline.

Example:

```python
def test_build_new_features():
    data = pd.DataFrame(
        {
            "observed_at": pd.to_datetime(
                [
                    "2026-01-01T00:00:00Z",
                    "2026-01-01T01:00:00Z",
                ],
                utc=True,
            ),
            "region": ["MISO", "MISO"],
            "value": [10.0, 12.0],
        }
    )

    result = build_new_features(data)

    assert len(result) == 2
    assert "example_feature" in result.columns
```

## 10. Run the Feature Stage

Run the configured feature:

```bash
uv run eml_transformer features \
    --name new_features \
    --config configs/dev.yaml
```

The feature pipeline will:

1. Load the feature definition.
2. Resolve the configured builder.
3. Read the input dataset.
4. Pass its DataFrame and settings to the builder.
5. Write the result to the configured Gold output.
6. Return a structured result to the CLI.

After the run, inspect:

- Output columns
- Row count
- Timestamp range
- Missing values
- Duplicate keys
- A sample of calculated features

## Checklist

### Feature Definition

- [ ] Define the single input dataset
- [ ] Define the output grain
- [ ] Identify required columns
- [ ] Choose the grouping keys
- [ ] Define timestamp and timezone behavior

### Implementation

- [ ] Add reusable transformations when appropriate
- [ ] Create the feature builder
- [ ] Accept one input DataFrame
- [ ] Validate required fields
- [ ] Return the completed DataFrame
- [ ] Keep storage operations outside the builder

### Registration and Configuration

- [ ] Register the builder
- [ ] Add the feature definition
- [ ] Configure one `input`
- [ ] Configure a Gold `output`
- [ ] Add builder settings when required

### Verification

- [ ] Add automated tests
- [ ] Run the feature stage
- [ ] Inspect the Gold output
- [ ] Confirm the output grain
- [ ] Check missing values and duplicates

## Related Documentation

- [Data Flow](../architecture/data-flow.md)
- [Storage Layout](../architecture/storage-layout.md)
- [Configuration](configuration.md)
- [Features Pipeline](../pipelines/features.md)
- [Adding a Dataset](adding-a-dataset.md)
- [Dataset References](../reference/dataset-references.md)