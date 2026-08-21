# Dataset Pipeline

The dataset pipeline combines one or more Gold feature sets into a model-ready dataset.

```text
Gold feature sets
    ↓
Registered dataset builder
    ↓
Gold model-ready dataset
```

The pipeline handles configuration, storage, builder selection, and result reporting. The selected builder contains the dataset-specific joining and validation logic.

## Responsibilities

The dataset pipeline:

1. Receives a typed `DatasetDefinition`.
2. Reads each configured input dataset.
3. Assigns each input to its configured alias.
4. Resolves the builder from the dataset registry.
5. Passes the input mapping and configured settings to the builder.
6. Writes the returned DataFrame to Gold storage.
7. Returns a `DatasetResult`.

## Configuration

A dataset definition can contain multiple named inputs.

```yaml
datasets:
  load_forecasting:
    enabled: true
    builder: load_forecast_dataset

    inputs:
      region_features: gold:eia_region_hourly:features
      interchange_features: gold:eia_interchange_hourly:features

    output: gold:load_forecasting:datasets

    settings:
      target: actual_load
```

| Field | Description |
|---|---|
| `name` | Name of the dataset definition. |
| `enabled` | Whether the dataset is available to configured workflows. |
| `builder` | Name of the registered dataset builder. |
| `inputs` | Maps builder input names to dataset references. |
| `output` | Logical reference for the completed Gold dataset. |
| `settings` | Keyword arguments passed to the builder. |

The input aliases become keys in the mapping passed to the builder:

```python
inputs["region_features"]
inputs["interchange_features"]
```

## Reading Inputs

The pipeline reads every configured input through the shared storage interface:

```python
inputs = {
    name: storage.read_dataset(ref)
    for name, ref in definition.inputs.items()
}
```

For the example configuration, the resulting mapping is:

```python
{
    "region_features": region_dataframe,
    "interchange_features": interchange_dataframe,
}
```

The builder uses these stable aliases rather than physical storage paths.

## Dataset Builders

The configured builder is resolved through the dataset registry:

```python
builder = get_dataset_function(
    definition.builder
)
```

A builder receives the named input mapping and configured settings:

```python
def build_load_forecast_dataset(
    inputs: Mapping[str, pd.DataFrame],
    *,
    target: str = "actual_load",
) -> pd.DataFrame:
    region_features = inputs["region_features"]
    interchange_features = inputs["interchange_features"]

    if target not in region_features.columns:
        raise ValueError(
            f"Target {target!r} is missing"
        )

    return region_features.merge(
        interchange_features,
        on=["observed_at", "region"],
        how="left",
        validate="one_to_one",
    )
```

Dataset builders are responsible for:

- Retrieving inputs by their configured aliases
- Validating required columns
- Validating the target
- Selecting join keys
- Defining join behavior
- Handling overlapping columns
- Preserving the intended row grain
- Returning the completed DataFrame

Builders should not read configuration files or access storage directly.

## Joining Feature Sets

Dataset builders should define joins explicitly.

```python
primary.merge(
    secondary,
    on=["observed_at", "region"],
    how="left",
    validate="one_to_one",
)
```

Important join decisions include:

- Join columns
- Join type
- Expected relationship
- Handling unmatched rows
- Handling duplicate keys
- Handling overlapping column names

Use merge validation whenever possible:

```text
one_to_one
many_to_one
one_to_many
```

Unexpected `_x` and `_y` columns should be prevented by removing redundant columns or renaming them before the merge.

## Writing the Dataset

The completed DataFrame is written using the configured output reference:

```python
storage.write_dataframe(
    ref=definition.output,
    frame=output,
)
```

For example:

```yaml
output: gold:load_forecasting:datasets
```

The storage layer resolves the logical reference to the appropriate local or S3 location.

## Dataset Result

The pipeline returns a `DatasetResult`.

```python
@dataclass(slots=True)
class DatasetResult:
    status: str
    name: str
    records_read: int = 0
    records_written: int = 0
    input_refs: tuple[str, ...] = ()
    output_ref: str | None = None
    error: str | None = None
```

### Result Fields

| Field | Description |
|---|---|
| `status` | Outcome of the dataset operation. |
| `name` | Configured dataset name. |
| `records_read` | Sum of the row counts from all input DataFrames. |
| `records_written` | Number of rows in the completed dataset. |
| `input_refs` | Dataset references used as inputs. |
| `output_ref` | Configured Gold output reference. |
| `error` | Error message when the operation fails. |

`records_read` represents the combined number of rows loaded across all inputs. It does not represent the number of unique observations after joining.

## Result Statuses

| Status | Meaning |
|---|---|
| `success` | The builder completed and the output was written. |
| `failed` | Reading, registry lookup, building, or writing raised an exception. |

The current implementation does not return separate `disabled`, `skipped`, or `empty` statuses.

## Failure Handling

The complete dataset operation runs inside one exception boundary.

Failures may include:

- Missing input datasets
- Invalid input types
- Unknown builder names
- Missing builder input aliases
- Missing target or join columns
- Duplicate join keys
- Builder exceptions
- Storage write failures

The exception is logged, and the pipeline returns:

```text
status: failed
records_read: 0
records_written: 0
error: <exception message>
```

## Running the Pipeline

Run one configured dataset:

```bash
uv run eml_transformer dataset \
    --name load_forecasting \
    --config configs/dev.yaml
```

Before running, confirm that:

- The dataset definition is enabled
- Its builder is registered
- Every input feature set exists
- Input aliases match those expected by the builder
- The upstream feature stages have completed

## Current Limitations

The pipeline currently loads every input dataset completely into memory and rebuilds the complete output.

Future improvements may include:

- Input type validation
- Enabled-definition checking
- Empty-input handling
- Output type validation
- Incremental dataset construction
- Date-bounded processing
- Configurable write modes
- Shared validation for timestamps and duplicate keys

The current implementation also writes the builder output without first confirming that it is a Pandas DataFrame. Builders must therefore follow the expected return contract.

## Related Documentation

- [Adding a Dataset](../guides/adding-a-dataset.md)
- [Configuration](../guides/configuration.md)
- [Data Flow](../architecture/data-flow.md)
- [Storage Layout](../architecture/storage-layout.md)
- [Features](features.md)
- [Modeling](modeling.md)