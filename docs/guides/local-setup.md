# Local Setup

This guide explains how to install and run the EML Energy Forecasting Pipeline locally.

The project uses:

- Python 3.10
- `uv` for Python and dependency management
- YAML configuration files
- Local filesystem storage by default

## Prerequisites

Install the following before continuing:

- Git
- `uv`
- A terminal environment such as Linux, macOS, or Windows Subsystem for Linux
- API credentials for any external sources you plan to use

Confirm that Git and `uv` are available:

```bash
git --version
uv --version
```

## 1. Clone the Repository

Clone the repository and enter its directory:

```bash
git clone <repository-url>
cd eml-transformer
```

Replace `<repository-url>` with the repository's Git URL.

## 2. Install Python

Install the required Python version through `uv`:

```bash
uv python install 3.10
```

Confirm the installed version:

```bash
uv run python --version
```

The output should report Python 3.10.

## 3. Install Dependencies

Install the project and its standard runtime dependencies:

```bash
uv sync
```

This creates a local virtual environment and installs the package using the versions recorded in `uv.lock`.

You do not need to activate the virtual environment when commands are run with `uv run`.

For example:

```bash
uv run eml_transformer --help
```

## 4. Install Optional Dependencies

Some functionality requires additional dependency groups.

Install notebook dependencies when using Jupyter:

```bash
uv sync --extra notebook
```

Install embedding dependencies when generating text embeddings:

```bash
uv sync --extra embeddings
```

Install both optional groups:

```bash
uv sync \
    --extra notebook \
    --extra embeddings
```

The embedding dependencies may be substantially larger because they include machine-learning libraries and embedding models.

## 5. Configure Environment Variables

Some sources require API keys.

Provide credentials through environment variables rather than writing secrets directly into YAML files.

For example:

```bash
export EIA_API_KEY="your-api-key"
export NEWS_API_KEY="your-api-key"
```

Environment-variable names are referenced by the source-specific configuration files.

```yaml
api_key_env: EIA_API_KEY
```

Only configure credentials for the sources you plan to enable.

For persistent local configuration, add the exports to your shell profile or use an environment-loading method that is excluded from version control.

Do not commit API keys, AWS credentials, or other secrets to the repository.

## 6. Review the Development Configuration

Local commands should use the development configuration:

```text
configs/dev.yaml
```

This file determines:

- The storage backend
- Enabled data sources
- Available processing stages
- Feature definitions
- Dataset definitions
- Model definitions
- Source-specific configuration paths

Local storage should be configured with a local root:

```yaml
storage:
  backend: local
  root: .
```

Source-specific settings are stored separately:

```text
configs/
└── sources/
    ├── eia_region.yaml
    ├── eia_interchange.yaml
    └── miso_notifications.yaml
```

Before running a workflow, confirm that the required sources and components are enabled.

## 7. Verify the Installation

Display the main CLI help:

```bash
uv run eml_transformer --help
```

Inspect the configured sources:

```bash
uv run eml_transformer inspect sources \
    --config configs/dev.yaml
```

Use the other inspection commands to verify configured features, datasets, and models.

If the CLI cannot find a component, confirm that:

- The component is enabled in `configs/dev.yaml`.
- Its configuration file exists.
- Its implementation is registered.
- The module containing the registration is imported.
- Required optional dependencies are installed.

## 8. Run a Small Ingestion Test

Begin with one source and a small request.

Run incremental ingestion:

```bash
uv run eml_transformer ingest \
    --source eia_region \
    --config configs/dev.yaml
```

The command should retrieve the currently available records and write them to the local Bronze layer.

After the run, inspect:

```text
data/bronze/
```

Confirm that:

- The source directory was created.
- Bronze records were written.
- The command completed without an unhandled error.
- No API credentials appeared in the logs.

## 9. Run Standardization

Convert the Bronze records into standardized Silver records:

```bash
uv run eml_transformer standardize \
    --source eia_region \
    --config configs/dev.yaml
```

Inspect the resulting data under:

```text
data/silver/
```

Silver data is stored as batches of Parquet files.

## 10. Run Additional Stages

Once ingestion and standardization work, run the stages required by the enabled configuration.

Examples include:

```bash
uv run eml_transformer features \
    --name eia_region_hourly \
    --config configs/dev.yaml
```

```bash
uv run eml_transformer dataset \
    --name load_forecasting \
    --config configs/dev.yaml
```

```bash
uv run eml_transformer train \
    --model miso_hourly_load_ridge \
    --config configs/dev.yaml
```

```bash
uv run eml_transformer forecast \
    --model miso_hourly_load_ridge \
    --config configs/dev.yaml
```

See the [CLI Reference](cli-reference.md) for the complete command syntax.

## 11. Run a Workflow

A workflow runs several related stages in sequence.

After verifying the individual stages, run the applicable development workflow:

```bash
uv run eml_transformer workflows numeric \
    --config configs/dev.yaml
```

Workflows use the enabled components and stages defined in the selected configuration.

Running stages individually first makes configuration or data problems easier to identify.

## 12. Start the API

Start the FastAPI development server:

```bash
uv run fastapi dev \
    src/eml_transformer/api/main.py
```

Alternatively, start it directly with Uvicorn:

```bash
uv run uvicorn eml_transformer.api.main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --reload
```

Open the API documentation:

```text
http://127.0.0.1:8000/docs
```

Check the health endpoint:

```bash
curl http://127.0.0.1:8000/health
```

The API reads from the storage backend defined by its configured runtime environment.

## 13. Run the Tests

Run the automated test suite:

```bash
uv run pytest
```

Run one test file:

```bash
uv run pytest tests/path/to/test_file.py
```

Run tests with more detailed output:

```bash
uv run pytest -v
```

Tests should use temporary storage and mocked external requests where practical.

## Local Output Directories

Local pipeline execution creates data and artifacts under:

```text
project/
├── data/
│   ├── bronze/
│   ├── silver/
│   ├── gold/
│   └── metadata/
└── artifacts/
    ├── models/
    └── experiments/
```

These directories contain generated outputs and should not normally be committed to version control.

See [Storage Layout](../architecture/storage-layout.md) for the complete organization.

## Updating Dependencies

After changing `pyproject.toml`, update the environment and lock file:

```bash
uv sync
```

To install the exact locked dependencies without updating them:

```bash
uv sync --frozen
```

Commit changes to both:

```text
pyproject.toml
uv.lock
```

when dependency definitions are intentionally updated.

## Common Setup Problems

### CLI command is not found

Run the command through `uv`:

```bash
uv run eml_transformer --help
```

Confirm that `uv sync` completed successfully.

### Incorrect Python version

Install and select Python 3.10:

```bash
uv python install 3.10
uv sync --python 3.10
```

### Missing optional dependency

Install the required optional group:

```bash
uv sync --extra embeddings
```

or:

```bash
uv sync --extra notebook
```

### Missing API key

Confirm that the required environment variable is set:

```bash
printenv EIA_API_KEY
```

Do not print the value in shared logs or screenshots.

### Source does not appear in inspection output

Confirm that:

- The source is enabled.
- The configuration name matches the registered source name.
- The source uses the registration decorator.
- Its module is imported through the appropriate `__init__.py`.

### No new records are retrieved

The source may not have published new records since the previous checkpoint.

Check:

- The ingestion checkpoint
- The configured lookback period
- The source's publication delay
- The requested start and end times
- API availability

A successful run with zero new records is not necessarily an error.

## Recommended Local Workflow

Use this sequence when working with a new component:

1. Review `configs/dev.yaml`.
2. Verify the component through the inspection command.
3. Run the relevant stage on a small input.
4. Inspect the output.
5. Run its automated tests.
6. Run the larger workflow only after the individual stage succeeds.

## Related Documentation

- [Configuration](configuration.md)
- [CLI Reference](cli-reference.md)
- [Project Structure](../architecture/project-structure.md)
- [Storage Layout](../architecture/storage-layout.md)
- [Data Flow](../architecture/data-flow.md)
- [Workflows](../operations/workflows.md)
- [Troubleshooting](../operations/troubleshooting.md)