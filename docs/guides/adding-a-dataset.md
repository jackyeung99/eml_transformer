# Adding a Dataset

This guide explains how to add a model-ready dataset.

A dataset builder combines one or more feature sets into a table designed for a forecasting task. The dataset pipeline loads the configured inputs, calls the builder, and writes the resulting Gold dataset.

## 1. Define the Forecasting Task

Before creating the dataset, identify:

- The prediction target
- The dataset frequency
- The row grain
- The geographic or market dimensions
- The required feature sets
- The join keys
- The expected model inputs

For example:

```text
Target: actual_load
Frequency: hourly
Grain: one row per observed_at and region
Inputs: regional features and interchange features
```

A clear grain is necessary to prevent ambiguous joins and duplicated observations.

## 2. Create the Dataset Builder

Add the builder to the datasets package.

```python
from collections.abc import Mapping

import pandas as pd


def build_new_dataset(
    inputs: Mapping[str, pd.DataFrame],
    *,
    target: str = "actual_load",
) -> pd.DataFrame:
    primary = inputs["primary_features"].copy()
    secondary = inputs["secondary_features"].copy()

    if target not in primary.columns:
        raise ValueError(
            f"Target {target!r} is missing from primary_features"
        )

    return primary.merge(
        secondary,
        on=["observed_at", "region"],
        how="left",
        validate="one_to_one",
    )
```

The builder should:

1. Retrieve feature sets using their configured aliases.
2. Validate the target and join columns.
3. Merge or align the feature sets.
4. Validate the resulting grain.
5. Return the model-ready DataFrame.

The builder should not load configuration or access storage directly.

## 3. Define Join Behavior Explicitly

Every merge should define:

- Join columns
- Join type
- Expected relationship
- Handling of unmatched records
- Handling of overlapping column names

Use Pandas merge validation when possible:

```python
validate="one_to_one"
```

Other valid relationships may include:

```python
validate="many_to_one"
validate="one_to_many"
```

Do not allow unexpected `_x` and `_y` columns. Remove redundant columns before the merge or rename fields to reflect their meaning.

## 4. Validate the Target

The dataset builder should verify that:

- The target column exists
- The target has an appropriate numeric type
- Target timestamps are valid
- Duplicate target observations are not introduced
- Missing target values are handled intentionally

Future rows used only for forecasting may not have known target values. Training and forecasting selection should distinguish these rows appropriately.

## 5. Register the Builder

Add the builder to the dataset registry.

```python
DATASET_BUILDERS = {
    "new_dataset_builder": build_new_dataset,
}
```

The registry connects the builder name in configuration to its Python implementation.

## 6. Add the Dataset Definition

Add a dataset definition to the configuration.

```yaml
datasets:
  new_forecasting_dataset:
    enabled: true
    builder: new_dataset_builder
    inputs:
      primary_features: gold:regional_hourly:features
      secondary_features: gold:interchange_hourly:features
    output: gold:new_forecasting_dataset:datasets
    settings:
      target: actual_load
```

The input aliases must match the keys expected by the builder.

## 7. Validate the Completed Dataset

Check the final dataset for:

- Expected columns
- Correct timestamp frequency
- Unique row keys
- Missing target values
- Missing feature values
- Unexpected merge losses
- Appropriate numeric types
- Correct ordering
- Timezone consistency

For time-series datasets, ensure that feature values do not use information that would have been unavailable at prediction time.

## 8. Test the Dataset Builder

Tests should cover:

- Successful merges
- Missing targets
- Missing join keys
- Duplicate input keys
- Unmatched input rows
- Overlapping column names
- Hourly or daily grain
- Multiple regions
- Empty inputs
- Prevention of target leakage

Use small feature DataFrames with clearly defined expected outputs.

## 9. Run the Dataset Stage

Run the configured dataset:

```bash
uv run eml_transformer dataset \
    --name new_forecasting_dataset \
    --config configs/dev.yaml
```

Inspect the output before connecting it to a model.

Confirm:

- Row count
- Date range
- Target availability
- Feature completeness
- Key uniqueness
- Expected training and forecasting rows

## Checklist

- [ ] Define the target and row grain
- [ ] Identify input feature sets
- [ ] Create the dataset builder
- [ ] Define joins and validation rules
- [ ] Validate the target
- [ ] Register the builder
- [ ] Add the dataset configuration
- [ ] Add automated tests
- [ ] Run and inspect the Gold dataset
- [ ] Check for target leakage

## Related Documentation

- [Data Flow](../architecture/data-flow.md)
- [Storage Layout](../architecture/storage-layout.md)
- [Configuration](configuration.md)
- [Datasets Pipeline](../pipelines/datasets.md)
- [Adding a Feature](adding-a-feature.md)
- [Adding a Model](adding-a-model.md)
- [Dataset References](../reference/dataset-references.md)