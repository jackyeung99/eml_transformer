# Configuration

The EML Energy Forecasting Pipeline uses YAML configuration files to control storage, sources, features, datasets, and models.

Configuration is loaded in two steps:

1. YAML files are read into ordinary Python dictionaries.
2. Loader functions validate and convert those dictionaries into typed configuration classes.

The typed classes provide a stable contract between configuration files and pipeline stages.

## Why Typed Configuration Is Used

The first pipeline implementations received generic dictionaries.

```python
def run_stage(config: dict[str, Any]) -> None:
    ...
```

This required each stage to assume that particular keys existed:

```python
builder = config["builder"]
input_ref = config["input"]
output_ref = config["output"]
```

This approach becomes fragile as the configuration grows. Misspelled or missing fields may not be discovered until a pipeline is already running.

The current design converts configuration into typed dataclasses before it reaches the pipelines.

```python
def run_feature(
    definition: FeatureDefinition,
) -> None:
    ...
```

The pipeline can now access a documented set of fields:

```python
builder = definition.builder
input_ref = definition.input
output_ref = definition.output
```

This provides:

- Clear inputs for each pipeline stage
- Earlier validation of required fields
- Better editor and type-checker support
- Consistent default values
- Less repeated dictionary parsing
- A clear boundary between configuration loading and execution

> **Important**
>
> Python dataclass type annotations do not validate YAML values automatically. The loader functions are responsible for checking required fields, applying defaults, converting collections, and constructing valid definitions.

## Configuration Flow

Configuration moves through the application in the following sequence:

```text
YAML files
    ↓
Raw dictionaries
    ↓
Loader and builder functions
    ↓
Typed configuration dataclasses
    ↓
AppConfig
    ↓
Runtime dependencies
    ↓
Pipeline stages
```

The pipelines should receive typed definitions rather than interpreting raw YAML dictionaries themselves.

## Configuration Classes

The primary configuration classes are:

| Class | Responsibility |
|---|---|
| `StorageConfig` | Defines the local or S3 storage backend. |
| `SourceDefinition` | Defines an external source and its allowed stages. |
| `FeatureDefinition` | Defines one input, a feature builder, and a Gold output. |
| `DatasetDefinition` | Defines multiple feature inputs, a dataset builder, and a Gold output. |
| `ModelDefinition` | Defines training, forecasting, model storage, and model settings. |
| `ExperimentDefinition` | Identifies an experimental workflow or configuration. |
| `AppConfig` | Contains the complete validated application configuration. |

## Immutable Configuration Objects

The dataclasses use:

```python
@dataclass(frozen=True, slots=True)
```

### `frozen=True`

`frozen=True` prevents fields from being reassigned after the object is created.

```python
definition.enabled = False
```

This raises an error rather than silently changing the configuration during a pipeline run.

Configuration should be treated as an input to the application, not mutable pipeline state.

### `slots=True`

`slots=True` restricts instances to their declared fields.

This helps prevent accidental attributes:

```python
definition.buidler = "incorrect_name"
```

It also makes the configuration objects smaller and communicates that their structure is fixed.

Nested dictionaries such as `settings` remain mutable objects unless they are copied or converted to immutable structures. The frozen dataclass prevents reassigning the field itself, but it does not make every nested value deeply immutable.

## Flexible Settings

Some fields remain generic mappings:

```python
Config = dict[str, Any]
```

These mappings are used when settings depend on a specific implementation.

For example, two sources may require completely different settings:

```yaml
respondent: MISO
measurement_types:
  - D
  - DF
```

```yaml
offices:
  - IND
  - IWX
products:
  - AFD
  - HWO
```

Similarly, model hyperparameters depend on the selected model:

```yaml
hyper_parameters:
  alpha: 1.0
```

```yaml
hyper_parameters:
  order:
    - 1
    - 1
    - 1
  seasonal_order:
    - 1
    - 0
    - 1
    - 24
```

Typed dataclasses define the fields shared by every component of that category. Flexible mappings contain implementation-specific options.

This provides structure without requiring a separate top-level configuration class for every source, builder, or model.

## `StorageConfig`

`StorageConfig` defines how data and artifacts are persisted.

```python
@dataclass(frozen=True, slots=True)
class StorageConfig:
    backend: str = "local"
    root: str = "."
    bucket: str | None = None
    prefix: str = ""
    region: str | None = None
    profile: str | None = None
    endpoint_url: str | None = None
```

| Field | Description |
|---|---|
| `backend` | Storage implementation to use, normally `local` or `s3`. |
| `root` | Root directory used by local storage. |
| `bucket` | S3 bucket name. |
| `prefix` | Optional prefix inside the S3 bucket. |
| `region` | AWS region used by the S3 client. |
| `profile` | Optional local AWS profile. |
| `endpoint_url` | Optional custom S3-compatible endpoint. |

Local example:

```yaml
storage:
  backend: local
  root: .
```

S3 example:

```yaml
storage:
  backend: s3
  bucket: eml-transformer
  prefix: ""
  region: us-east-2
```

The loader should reject unsupported backends and require a bucket when `backend` is `s3`.

## `SourceDefinition`

`SourceDefinition` describes an enabled external data source.

```python
@dataclass(frozen=True, slots=True)
class SourceDefinition:
    name: str
    enabled: bool
    stages: frozenset[str]
    settings: Config = field(default_factory=dict)
```

| Field | Description |
|---|---|
| `name` | Registered source name. |
| `enabled` | Whether the source is available to workflows. |
| `stages` | Processing stages in which the source participates. |
| `settings` | Source-specific settings loaded from its configuration file. |

The loader converts the YAML stage list into a `frozenset`:

```yaml
stages:
  - ingest
  - backfill
  - standardize
```

```python
frozenset(
    {
        "ingest",
        "backfill",
        "standardize",
    }
)
```

A set provides efficient membership checks:

```python
if "backfill" in definition.stages:
    ...
```

The main configuration points to the source-specific settings file:

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

The loader reads `configs/sources/eia_region.yaml` and stores its contents in `definition.settings`.

## `FeatureDefinition`

`FeatureDefinition` describes one feature-building operation.

```python
@dataclass(frozen=True, slots=True)
class FeatureDefinition:
    name: str
    enabled: bool
    builder: str
    input: str
    output: str
    settings: Config = field(default_factory=dict)
```

| Field | Description |
|---|---|
| `name` | Name of the configured feature set. |
| `enabled` | Whether the feature can be built. |
| `builder` | Registered feature-builder name. |
| `input` | Logical reference for the single input dataset. |
| `output` | Logical reference for the Gold feature output. |
| `settings` | Keyword arguments passed to the builder. |

Example:

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

The feature pipeline receives a `FeatureDefinition`, resolves its builder, reads its single input, and writes the returned DataFrame to its output.

## `DatasetDefinition`

`DatasetDefinition` describes how multiple feature sets are combined into a model-ready dataset.

```python
@dataclass(frozen=True, slots=True)
class DatasetDefinition:
    name: str
    enabled: bool
    builder: str
    inputs: dict[str, str]
    output: str
    settings: Config = field(default_factory=dict)
```

| Field | Description |
|---|---|
| `name` | Name of the configured dataset. |
| `enabled` | Whether the dataset can be built. |
| `builder` | Registered dataset-builder name. |
| `inputs` | Maps builder input aliases to logical dataset references. |
| `output` | Logical reference for the Gold dataset output. |
| `settings` | Keyword arguments passed to the builder. |

Example:

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

The input names become keys in the mapping passed to the builder:

```python
inputs["region_features"]
inputs["interchange_features"]
```

Features accept one input, while datasets can combine multiple feature sets.

## `ModelDefinition`

`ModelDefinition` contains the configuration required for training and forecasting.

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

### Identity and Selection

| Field | Description |
|---|---|
| `name` | Configured model name. |
| `enabled` | Whether the model is available to the modeling pipeline. |
| `model_type` | Registered forecasting-model implementation. |

### Inputs and Outputs

| Field | Description |
|---|---|
| `training_input` | Dataset used for model fitting and validation. |
| `forecast_input` | Dataset used to construct forecast inputs. |
| `model_output` | Location or identifier for the trained model artifact. |
| `forecast_output` | Gold dataset reference for generated forecasts. |

### Modeling Behavior

| Field | Description |
|---|---|
| `target` | Column predicted by the model. |
| `features` | Ordered feature columns used by exogenous models. |
| `retrain_after_hours` | Minimum model age before automatic retraining. |
| `hyper_parameters` | Settings passed to the model implementation. |
| `training_settings` | Training-window and validation behavior. |
| `forecast_settings` | Forecast horizon, frequency, and preparation behavior. |

Example:

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
      - actual_load_lag_24
      - actual_load_lag_168

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

The loader converts the feature list into a tuple so the expected feature order remains stable:

```python
features=(
    "hour",
    "month",
    "is_weekend",
    "actual_load_lag_24",
    "actual_load_lag_168",
)
```

## `ExperimentDefinition`

`ExperimentDefinition` identifies an experiment.

```python
@dataclass(frozen=True, slots=True)
class ExperimentDefinition:
    name: str
```

The current definition is intentionally minimal. It can later be expanded to include:

- Dataset selection
- Model selection
- Backtesting windows
- Evaluation metrics
- Hyperparameter search
- Output artifact locations

## `AppConfig`

`AppConfig` contains the complete loaded application configuration.

```python
@dataclass(frozen=True, slots=True)
class AppConfig:
    storage: StorageConfig
    sources: dict[str, SourceDefinition]
    embeddings: Config
    features: dict[str, FeatureDefinition]
    datasets: dict[str, DatasetDefinition]
    modeling: dict[str, ModelDefinition]
```

Instead of passing unrelated dictionaries throughout the application, the runtime holds one structured configuration object.

Examples:

```python
config.storage
config.sources["eia_region"]
config.features["eia_region_hourly"]
config.datasets["load_forecasting"]
config.modeling["miso_hourly_load_ridge"]
```

The mapping keys allow definitions to be selected by their configured names.

## Configuration Loaders

Loader functions sit between the YAML files and the typed dataclasses.

Their responsibilities include:

1. Reading the main YAML file.
2. Confirming that top-level sections have the expected structure.
3. Loading referenced component configuration files.
4. Applying default values.
5. Validating required fields.
6. Converting YAML values into the expected Python collections.
7. Constructing typed definition objects.
8. Returning the completed `AppConfig`.

Conceptually:

```python
raw_config = read_yaml(path)

storage = build_storage_config(
    raw_config.get("storage", {})
)

sources = {
    name: build_source_definition(name, values)
    for name, values in raw_config.get("sources", {}).items()
}

features = {
    name: build_feature_definition(name, values)
    for name, values in raw_config.get("features", {}).items()
}

datasets = {
    name: build_dataset_definition(name, values)
    for name, values in raw_config.get("datasets", {}).items()
}

models = {
    name: build_model_definition(name, values)
    for name, values in raw_config.get("modeling", {}).items()
}

config = AppConfig(
    storage=storage,
    sources=sources,
    embeddings=raw_config.get("embeddings", {}),
    features=features,
    datasets=datasets,
    modeling=models,
)
```

The exact implementation may differ, but the boundary should remain the same:

```text
Loaders interpret configuration.
Pipelines consume typed definitions.
```

## Loader Validation

Loaders should report configuration errors before a pipeline begins expensive work.

Useful validation includes:

- Required fields are present
- Values have the expected type
- Names are not empty
- Storage backends are supported
- Dataset references have valid layers
- Source stages are allowed
- Referenced component files exist
- Feature inputs and outputs are defined
- Dataset input mappings are valid
- Model targets and outputs are configured
- Numeric settings are within valid ranges

A useful error identifies both the definition and the invalid field:

```text
Feature 'eia_region_hourly' is missing required field 'input'.
```

This is more useful than allowing a later `KeyError` inside the feature pipeline.

## Runtime Dependencies

Configuration describes what the application should use. The runtime creates the objects required to perform that work.

The runtime is built once for an application entry point:

```python
runtime = build_runtime(
    Path("configs/dev.yaml")
)
```

Conceptually, runtime construction performs the following work:

```text
Configuration path
    ↓
Load AppConfig
    ↓
Create StoragePaths
    ↓
Create LocalStorage or S3Storage
    ↓
Assemble Runtime
```

A runtime may contain:

- The loaded `AppConfig`
- The selected storage implementation
- Shared storage paths
- Other application-wide dependencies

For example:

```python
@dataclass(frozen=True, slots=True)
class Runtime:
    config: AppConfig
    storage: Storage
    paths: StoragePaths
```

The exact fields may evolve, but the purpose is to construct shared dependencies in one place.

## Why Runtime Construction Is Separate

Configuration objects contain values:

```python
StorageConfig(
    backend="s3",
    bucket="eml-transformer",
    region="us-east-2",
)
```

Runtime dependencies contain working implementations:

```python
S3Storage(
    bucket="eml-transformer",
    region="us-east-2",
)
```

This separation keeps configuration declarative.

```text
StorageConfig describes the backend.
S3Storage performs storage operations.
```

The same distinction applies throughout the system:

```text
FeatureDefinition describes a feature operation.
The feature registry resolves its builder.
The feature pipeline executes it.
```

```text
ModelDefinition describes a forecasting model.
The model registry resolves its implementation.
The modeling pipeline trains or runs it.
```

## Pipelines and Typed Definitions

Each pipeline receives the definition associated with its responsibility.

```python
feature_pipeline.build(
    definition=config.features["eia_region_hourly"]
)
```

```python
dataset_pipeline.build(
    definition=config.datasets["load_forecasting"]
)
```

```python
modeling_pipeline.train(
    definition=config.modeling["miso_hourly_load_ridge"]
)
```

The pipeline does not need to know how the original YAML was structured or where an external configuration file was stored. It receives a completed, typed definition.

A pipeline then uses the definition to:

1. Resolve a registered implementation.
2. Read the configured inputs.
3. Pass implementation-specific settings.
4. Run the operation.
5. Write the configured output.
6. Return a structured result.

## Flexible Settings and Validation Boundaries

Generic `settings` mappings provide flexibility, but they should not become an alternative to typed top-level fields.

Use a typed dataclass field when:

- Every definition of that category requires the value.
- The pipeline itself reads the value.
- The value affects orchestration or storage.
- The value has consistent meaning across implementations.

Use `settings` when:

- The value belongs to one builder or source.
- Different implementations require different options.
- The value is passed directly to a registered implementation.

For example:

```yaml
features:
  eia_region_hourly:
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

Here:

- `builder`, `input`, and `output` are part of every feature definition.
- `timezone` and `load_lags` belong specifically to this builder.

Implementation-specific settings should be validated by the component that understands them or by a dedicated component-specific loader.

## Summary

The configuration system separates raw files, typed definitions, runtime dependencies, and execution.

```text
YAML
    ↓
Loader validation
    ↓
Typed dataclasses
    ↓
Runtime dependencies
    ↓
Pipeline execution
```

Each layer has a distinct responsibility:

| Layer | Responsibility |
|---|---|
| YAML files | Allow users to define runtime behavior. |
| Loaders | Read, validate, convert, and combine configuration. |
| Typed dataclasses | Define the inputs expected by each pipeline. |
| Runtime | Creates shared working dependencies from configuration. |
| Pipelines | Execute operations using typed definitions and runtime dependencies. |
| Registries | Resolve configured names to component implementations. |

This structure prevents pipeline stages from guessing which dictionary keys are available and keeps configuration parsing separate from processing logic.

## Related Documentation

- [Local Setup](local-setup.md)
- [CLI Reference](cli-reference.md)
- [Adding a Source](adding-a-source.md)
- [Adding a Feature](adding-a-feature.md)
- [Adding a Dataset](adding-a-dataset.md)
- [Adding a Model](adding-a-model.md)
- [Configuration Schema](../reference/configuration-schema.md)
- [Design Principles](../architecture/design-principles.md)
- [Project Structure](../architecture/project-structure.md)