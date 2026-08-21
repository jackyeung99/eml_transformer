# Modeling Pipeline

The modeling pipeline trains forecasting models, stores model artifacts and metadata, and generates forecasts.

It contains three high-level operations:

| Operation | Purpose | Status |
|---|---|---|
| `train()` | Fits and evaluates a configured model. | Implemented |
| `forecast()` | Loads a trained model and generates future predictions. | Implemented |
| `experiment()` | Runs backtests and model comparisons. | Planned |

```text
Model-ready dataset
    ↓
Training
    ↓
Model artifact and metadata
    ↓
Forecasting
    ↓
Gold forecast records
```

## Model Definition

Training and forecasting receive the same typed `ModelDefinition`.

```python
@dataclass(frozen=True, slots=True)
class ModelDefinition:
    name: str
    enabled: bool
    model_type: str

    training_input: str
    forecast_input: str
    model_output: str
    forecast_output: str

    target: str
    retrain_after_hours: int | None

    hyper_parameters: dict[str, Any]
    training_settings: dict[str, Any]
    forecast_settings: dict[str, Any]

    features: tuple[str, ...] = ()
```

| Field | Description |
|---|---|
| `name` | Name of the configured model. |
| `enabled` | Whether the model is available to workflows. |
| `model_type` | Registered model implementation. |
| `training_input` | Model-ready dataset used for training. |
| `forecast_input` | Dataset used to construct future inputs. |
| `model_output` | Identifier used to store the model and metadata. |
| `forecast_output` | Gold reference used to store forecasts. |
| `target` | Column predicted by the model. |
| `features` | Ordered feature columns used by an exogenous model. |
| `retrain_after_hours` | Minimum model age before automatic retraining. |
| `hyper_parameters` | Settings passed to the model implementation. |
| `training_settings` | Training-window and validation settings. |
| `forecast_settings` | Forecast horizon, frequency, and timestamp settings. |

The pipeline itself does not currently check `definition.enabled`. The CLI or workflow should avoid passing disabled definitions to it.

## Configuration Example

```yaml
modeling:
  miso_hourly_load_ridge:
    enabled: true
    model_type: ridge

    training_input: gold:load_forecasting:datasets
    forecast_input: gold:load_forecasting:datasets

    model_output: miso_hourly_load_ridge
    forecast_output: gold:miso_hourly_load_ridge:forecasts

    target: actual_load

    features:
      - hour
      - month
      - is_weekend
      - is_holiday
      - actual_load_lag_24
      - actual_load_lag_168
      - total_imports_lag_24
      - total_exports_lag_24

    retrain_after_hours: 168

    hyper_parameters:
      alpha: 1.0

    training_settings:
      timestamp_column: observed_at
      lookback_days: 730
      validation_days: 14

    forecast_settings:
      timestamp_column: observed_at
      forecast_steps: 24
      frequency: 1h
```

## Training

The training operation determines whether a model needs to be retrained, loads its historical dataset, fits and evaluates the selected model, and stores the resulting artifacts.

```text
Model definition
    ↓
Read existing metadata
    ↓
Evaluate retraining decision
    ↓
Read training dataset
    ↓
Create registered model
    ↓
Time-based training and validation
    ↓
Create model metadata
    ↓
Write model artifacts
```

## Retraining Decision

Before loading the training dataset, the pipeline checks for existing model metadata:

```python
existing_metadata = storage.read_model_metadata(
    definition.model_output
)
```

If `force=True`, the model is always trained:

```python
TrainingDecision(
    should_train=True,
    reason="Training was forced",
)
```

Otherwise, `should_train()` evaluates:

- Whether a model already exists
- When it was last trained
- The configured `retrain_after_hours`

If retraining is not required, the pipeline returns a skipped result without reading the training dataset.

```text
status: skipped
reason: <training decision>
```

This prevents scheduled workflows from fitting an unchanged model during every run.

### Forced Training

Force training through the CLI when supported:

```bash
uv run eml_transformer train \
    --model miso_hourly_load_ridge \
    --force \
    --config configs/dev.yaml
```

Forced training is useful after:

- Changing the model configuration
- Changing the training dataset
- Fixing a feature or target
- Testing model behavior
- Intentionally replacing the current artifact

## Reading Training Data

When training is required, the pipeline loads:

```python
data = storage.read_dataset(
    definition.training_input
)
```

If the dataset is empty, training returns `skipped`.

The modeling pipeline currently reads the complete model-ready dataset into memory. The configured lookback is applied later by the training helper.

## Model Creation

The model is created through the model registry:

```python
model = create_model(
    definition.model_type,
    definition.hyper_parameters,
)
```

Conceptually:

```text
Configured model type
    ↓
Model registry
    ↓
Forecast model implementation
```

This allows the same pipeline to train different models without containing model-specific construction logic.

Examples include:

- Ridge regression
- Random forest
- ARIMA
- SARIMAX
- Custom forecasting models

## Time-Based Training and Validation

The pipeline passes the dataset and model settings to `train_model()`:

```python
trained = train_model(
    model,
    data,
    features=definition.features,
    target=definition.target,
    timestamp_column=...,
    lookback_days=...,
    validation_days=...,
)
```

Default settings are:

| Setting | Default |
|---|---:|
| `timestamp_column` | `observed_at` |
| `lookback_days` | `730` |
| `validation_days` | `14` |

The most recent validation period is held out from model fitting.

```text
Historical lookback period
├───────────────────────────┬───────────────┤
       Training data           Validation data
                                Most recent
                                validation days
```

This preserves time order and avoids randomly mixing future observations into the training period.

The training helper returns information including:

- Fitted model
- Feature columns
- Target column
- Records used
- Records trained
- Records validated
- Training period
- Validation period
- Evaluation metrics
- Model diagnostics

## Model Metadata

After training, the pipeline creates a unique model version from the training time.

It then stores `ModelMetadata` containing:

- Model name
- Model type
- Model version
- Training time
- Expected features
- Target
- Records used
- Records trained
- Records validated
- Hyperparameters
- Training settings
- Evaluation metrics
- Diagnostics
- Training date range
- Validation date range

The metadata is an important contract between training and forecasting.

Forecasting uses the features stored in the model metadata rather than assuming the current configuration still matches the fitted model.

## Model Artifacts

The trained model and metadata are written together:

```python
storage.write_model(
    definition.model_output,
    trained.model,
    metadata,
)
```

A local model directory may look like:

```text
artifacts/models/model=miso_hourly_load_ridge/
├── model.joblib
└── metadata.json
```

The same logical artifact structure can be stored in Amazon S3.

## Training Results

Training returns a `TrainingResult`.

Common statuses include:

| Status | Meaning |
|---|---|
| `success` | The model was fitted, evaluated, and stored. |
| `skipped` | Retraining was unnecessary or the dataset was empty. |
| `failure` | Training raised an exception. |

A successful result reports:

- Model name
- Retraining reason
- Records read
- Records trained
- Records validated
- Evaluation metrics
- Model reference
- Training time

## Forecasting

The forecasting operation loads a trained model and its metadata, reads the configured forecast input, creates future timestamps and features, generates predictions, and writes Gold forecast records.

```text
Stored model and metadata
          +
Forecast input dataset
          ↓
Resolve forecast origin
          ↓
Create future timestamps
          ↓
Prepare exogenous features when required
          ↓
model.forecast()
          ↓
Create forecast records
          ↓
Write Gold forecasts
```

## Loading Forecast Inputs

The pipeline loads the model and metadata:

```python
model, metadata = storage.read_model(
    definition.model_output
)
```

It then reads the configured dataset:

```python
forecast_data = storage.read_dataset(
    definition.forecast_input
)
```

If the forecast dataset is empty, the operation returns `skipped`.

Forecasting requires an existing trained model. If the artifact cannot be loaded, the pipeline returns a failure result.

## Forecast Settings

The forecasting operation supports:

| Setting | Default | Description |
|---|---:|---|
| `timestamp_column` | `observed_at` | Canonical time column in the input dataset. |
| `forecast_steps` | `1` | Number of future predictions to generate. |
| `frequency` | `1h` | Spacing between target timestamps. |

Example:

```yaml
forecast_settings:
  timestamp_column: observed_at
  forecast_steps: 24
  frequency: 1h
```

`forecast_steps` must be positive, and `frequency` must be recognized by Pandas.

## Forecast Origin

The current pipeline does not explicitly provide a forecast origin, so `generate_forecast()` infers it from the input data.

The origin is the latest timestamp with a known target value:

```text
forecast_origin =
    maximum timestamp where target is not missing
```

If the target column is missing or contains no observed values, the origin cannot be inferred and forecasting fails.

This prevents future placeholder rows with missing targets from being mistaken for observed history.

## Future Timestamps

Future target timestamps are created from:

- Forecast origin
- Forecast steps
- Forecast frequency
- Market timezone

The market timezone is currently:

```text
America/New_York
```

The date range is constructed in Eastern time and then converted back to UTC.

This is particularly important for daily forecasts because Eastern calendar days may contain 23 or 25 hours during daylight-saving-time transitions.

The pipeline retains:

- Canonical UTC timestamps for storage and comparison
- Eastern timestamps for user-facing interpretation

## Models Without Exogenous Features

If:

```python
model.requires_exogenous is False
```

the pipeline calls the model without a future feature frame:

```python
model.forecast(
    steps=forecast_steps,
    X=None,
)
```

This is appropriate for models that generate forecasts only from their fitted target history.

## Models With Exogenous Features

If:

```python
model.requires_exogenous is True
```

the pipeline constructs a future DataFrame containing the features stored in `ModelMetadata`.

Future features are divided into two categories.

### Known Calendar Features

Calendar features can be calculated directly from future timestamps:

- `hour`
- `day_of_week`
- `day_name`
- `day_type`
- `month`
- `is_weekend`
- `is_holiday`

These values are recalculated for every future target time and are never forward-filled.

Eastern time is derived first so these features reflect the local market calendar.

### Other Exogenous Features

Other features may not be known over the complete forecast horizon.

Examples include:

- Lagged target values
- Rolling target statistics
- Future load or generation values
- Future interchange values
- Weather-derived variables
- Other source-derived measurements

The current implementation takes the latest available nonmissing value at or before the forecast origin and carries it across every future row.

```text
Latest known value
    ↓
Step 1
Step 2
Step 3
...
Step N
```

The pipeline validates that every required feature exists and that the prepared future feature frame contains no missing values.

> **Future improvement: exogenous forecasting**
>
> The current handling of non-calendar exogenous variables is a temporary solution. Carrying the latest value forward assumes that the variable remains unchanged throughout the forecast horizon.
>
> This may be particularly inaccurate for lagged targets, interchange, load, generation, weather, and other time-varying inputs.
>
> Future work should support per-feature strategies such as:
>
> - Known future values loaded from another dataset
> - Weather or market forecasts
> - Separate forecasts for exogenous variables
> - Recursive use of model predictions
> - Scenario-based future values
> - Bounded forward-filling for appropriate variables
>
> Known calendar features should continue to be calculated directly from future timestamps rather than forward-filled.

## Prediction Validation

The model must return exactly one prediction for every requested forecast step.

```python
if len(predictions) != forecast_steps:
    raise ValueError(...)
```

This prevents incomplete or misaligned forecasts from being stored.

Predictions are flattened into a one-dimensional sequence before the forecast records are created.

## Forecast Record Schema

Each generated forecast row contains:

| Field | Description |
|---|---|
| `forecast_id` | Stable identifier for the forecast record. |
| `model_name` | Configured model name. |
| `model_type` | Model implementation type. |
| `model_version` | Version of the fitted model. |
| `model_trained_at` | Time the model was trained. |
| `generated_at_utc` | Time the forecast run occurred. |
| `forecast_origin_utc` | Latest observed target time used as the forecast origin. |
| `forecast_for_utc` | Future UTC target time being predicted. |
| `generated_at_et` | Forecast creation time in Eastern time. |
| `forecast_origin_et` | Forecast origin in Eastern time. |
| `forecast_for_et` | Forecast target time in Eastern time. |
| `horizon` | Forecast step beginning at `1`. |
| `predicted_value` | Generated prediction. |

The stable forecast identifier is derived from:

```text
model name
model version
forecast origin
forecast target time
```

This distinguishes model versions and target timestamps while allowing the same logical forecast record to be identified consistently.

## Forecast Storage

Forecasts are written through:

```python
storage.write_forecasts(
    definition.forecast_output,
    generated.records,
)
```

For example:

```yaml
forecast_output: gold:miso_hourly_load_ridge:forecasts
```

Forecasts are Gold data products rather than model artifacts.

```text
Model:
artifacts/models/model=miso_hourly_load_ridge/

Forecasts:
data/gold/forecasts/dataset=miso_hourly_load_ridge/
```

## Forecast Results

Forecasting returns a `ForecastResult`.

Common statuses include:

| Status | Meaning |
|---|---|
| `success` | Forecast records were generated and written. |
| `skipped` | The forecast input dataset was empty. |
| `failure` | Model loading, input preparation, prediction, or writing failed. |

A successful result reports:

- Model name
- Records read
- Forecast records written
- Model reference
- Forecast reference
- Model version
- Forecast origin
- Generation time

## Running the Modeling Pipeline

Train a model:

```bash
uv run eml_transformer train \
    --model miso_hourly_load_ridge \
    --config configs/dev.yaml
```

Force retraining:

```bash
uv run eml_transformer train \
    --model miso_hourly_load_ridge \
    --force \
    --config configs/dev.yaml
```

Generate a forecast:

```bash
uv run eml_transformer forecast \
    --model miso_hourly_load_ridge \
    --config configs/dev.yaml
```

## Experiments

The pipeline includes an `experiment()` method, but experiment execution is not currently implemented.

```python
raise NotImplementedError(
    "Experiment execution is not implemented"
)
```

Future experiment support may include:

- Backtesting
- Model comparison
- Hyperparameter testing
- Feature evaluation
- Forecast-error analysis

Experiments should reuse the same model definitions, datasets, metrics, and artifact conventions where practical.

## Current Limitations

The current modeling implementation has several areas for future improvement:

- Complete datasets are loaded into memory.
- Non-calendar exogenous values are forward-filled across the horizon.
- Forecast origin is inferred rather than configurable through the pipeline.
- Experiment execution is not implemented.
- The pipeline itself does not check whether a model definition is enabled.
- Model and forecast validation could be expanded.
- Backtesting should be separated from operational forecast generation.

## Related Documentation

- [Adding a Model](../guides/adding-a-model.md)
- [Adding a Dataset](../guides/adding-a-dataset.md)
- [Configuration](../guides/configuration.md)
- [Data Flow](../architecture/data-flow.md)
- [Storage Layout](../architecture/storage-layout.md)
- [Datasets](datasets.md)
- [Experiments](experiments.md)
- [Troubleshooting](../operations/troubleshooting.md)