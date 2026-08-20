# Adding a Model

This guide explains how to add a forecasting model implementation.

A model implementation contains model-specific fitting and prediction behavior. The modeling pipeline handles configuration, dataset loading, training windows, evaluation, artifact storage, and forecast output.

## 1. Determine the Model Requirements

Before implementing a model, define:

- The prediction target
- Whether the model uses exogenous features
- The expected input format
- The forecast frequency
- The supported forecast horizon
- Required hyperparameters
- How the model produces multi-step forecasts

A model should follow the shared forecasting interface so it can be used by the existing training and forecasting pipelines.

## 2. Create the Model Class

Add the implementation under the modeling package.

```text
src/eml_transformer/modeling/models/
└── new_model.py
```

The model should extend the shared base model.

```python
from __future__ import annotations

import pandas as pd

from eml_transformer.modeling.models.base import BaseForecastModel


class NewForecastModel(BaseForecastModel):
    @property
    def requires_exogenous(self) -> bool:
        return True

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
    ) -> NewForecastModel:
        # Fit the underlying model.
        return self

    def predict(
        self,
        X: pd.DataFrame,
    ):
        # Return predictions aligned with X.
        ...
```

The exact methods depend on the shared base interface and whether the model performs direct prediction, recursive forecasting, or native time-series forecasting.

## 3. Keep Pipeline Responsibilities Separate

The model implementation should contain model-specific behavior, such as:

- Constructing the underlying estimator
- Applying hyperparameters
- Fitting the estimator
- Generating predictions
- Handling model-specific forecast behavior

The model should not be responsible for:

- Reading YAML configuration
- Loading datasets from storage
- Selecting training windows
- Writing model artifacts
- Formatting CLI output
- Writing forecast records

These responsibilities belong to the modeling pipeline.

## 4. Handle Exogenous Features

Use the shared model interface to indicate whether the model requires exogenous inputs.

Examples include:

- Ridge regression requires feature columns.
- Random forest requires feature columns.
- SARIMAX may optionally use exogenous variables.
- ARIMA may operate only on the target history.

If exogenous features are required, document:

- Expected feature columns
- Missing-value behavior
- Column ordering requirements
- Future feature requirements

The forecasting stage must be able to construct every required feature for each future target time. 

> **Future improvement**
>
> The current handling of exogenous variables during multi-step forecasting is limited. A model may require a complete feature row for every future target time, but many exogenous variables are not known across the full forecast horizon.
>
> Some future features can be calculated exactly, including:
>
> - Hour
> - Day of week
> - Month
> - Weekend indicators
> - Holiday indicators
>
> Other features depend on values that have not yet been observed, including:
>
> - Lagged target values
> - Rolling target statistics
> - Future load or generation measurements
> - Future interchange values
> - Other source-derived variables
>
> The current implementation may carry the latest available exogenous values forward to complete the future feature rows. This allows forecasting to run, but it assumes those variables remain unchanged throughout the forecast horizon and may reduce forecast accuracy.
>
> A more robust implementation should distinguish between known-future features and unknown-future features. Unknown values could be handled through recursive prediction, separate forecasts for exogenous variables, scenario assumptions, or models that do not require those variables across the full horizon.
>
> This limitation and its proposed improvements are tracked in the [Future Work](../to-do.md) documentation.


## 5. Validate Hyperparameters

Read model-specific hyperparameters from the configured model definition.

Example:

```yaml
hyper_parameters:
  alpha: 1.0
```

The model implementation should validate important constraints and provide clear errors for invalid values.

Avoid silently accepting unsupported parameters.

## 6. Register the Model

Add the implementation to the model registry.

```python
MODEL_FACTORIES = {
    "new_model": NewForecastModel,
}
```

If the registry uses factory functions, construct and return the model using the configured hyperparameters:

```python
def create_new_model(**parameters):
    return NewForecastModel(**parameters)
```

The registry name becomes the configured `model_type`.

## 7. Add the Model Definition

Add the model to the YAML configuration.

```yaml
modeling:
  new_load_model:
    enabled: true
    model_type: new_model

    training_input: gold:load_forecasting:datasets
    forecast_input: gold:load_forecasting:datasets

    model_output: new_load_model
    forecast_output: gold:new_load_model:forecasts

    target: actual_load

    features:
      - hour
      - month
      - is_weekend
      - actual_load_lag_24

    retrain_after_hours: 168

    hyper_parameters:
      alpha: 1.0

    training_settings:
      time_column: observed_at
      lookback_days: 730
      validation_days: 14

    forecast_settings:
      forecast_steps: 24
      frequency: 1h
```

The exact settings depend on the model.

A univariate model may not require a `features` list, while an exogenous model must define every required input column.

## 8. Confirm Artifact Compatibility

Training writes:

- A serialized model
- Model metadata
- Evaluation metrics
- Expected features and target information

Verify that the model can be serialized and loaded using the project's artifact mechanism.

The loaded model should produce the same predictions as the original fitted model when given the same input.

## 9. Test the Model

Tests should cover:

- Successful fitting
- Prediction shape
- Feature requirements
- Invalid hyperparameters
- Missing columns
- Empty input data
- Serialization and loading
- Deterministic behavior when a random seed is configured
- Multi-step forecast behavior
- Forecast index alignment

Model tests should use small synthetic datasets and should not depend on production data.

## 10. Run Training

Train the configured model:

```bash
uv run eml_transformer train \
    --model new_load_model \
    --config configs/dev.yaml
```

Review:

- Training period
- Validation period
- Evaluation metrics
- Selected features
- Stored model metadata

## 11. Run Forecasting

Generate a forecast:

```bash
uv run eml_transformer forecast \
    --model new_load_model \
    --config configs/dev.yaml
```

Inspect:

- Forecast creation time
- Target timestamps
- Prediction frequency
- Forecast horizon
- Missing predictions
- Model identifier
- Output dataset reference

## Checklist

- [ ] Define the model's input and forecast requirements
- [ ] Implement the shared model interface
- [ ] Keep storage and orchestration outside the model
- [ ] Define exogenous feature requirements
- [ ] Validate hyperparameters
- [ ] Register the model
- [ ] Add the model configuration
- [ ] Verify serialization
- [ ] Add automated tests
- [ ] Run training and inspect metrics
- [ ] Run forecasting and inspect stored predictions

## Related Documentation

- [Architecture Overview](../architecture/overview.md)
- [Design Principles](../architecture/design-principles.md)
- [Configuration](configuration.md)
- [Modeling Pipeline](../pipelines/modeling.md)
- [Adding a Dataset](adding-a-dataset.md)
- [Configuration Schema](../reference/configuration-schema.md)
- [Schemas](../reference/schemas.md)