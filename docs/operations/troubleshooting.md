# Troubleshooting

## Component Is Unknown

Use the inspection commands to confirm configuration and registration:

```bash
uv run eml_transformer show sources --config configs/dev.yaml
uv run eml_transformer show features --config configs/dev.yaml
uv run eml_transformer show datasets --config configs/dev.yaml
uv run eml_transformer show models --config configs/dev.yaml
```

For a source, confirm that its module is imported by the appropriate `__init__.py` so `@register_source` executes.

## Stage Is Unsupported

Confirm that the source lists the stage in the main configuration. Valid source stages are `ingest`, `backfill`, `standardize`, `scrape`, and `embed`.

## Missing API Key

Set the environment variable named by `api_key_env`. The loader intentionally does not store resolved secrets in `AppConfig`; ingestion resolves them immediately before source construction.

## No New Records

This may be normal. Check source publication time, the requested window, checkpoint value, lookback period, source filters, and deduplication counts.

## Missing Downstream Input

Run the upstream stage first: Bronze is required for standardization, Silver for features or embeddings, feature sets for datasets, datasets for training, and a trained artifact for forecasting.

## Forecasting Fails on Features

Check that every feature stored in model metadata can be constructed for the future horizon. Calendar features are derived; non-calendar exogenous features currently require a known value at or before the origin.

## ECS Task Stops

Inspect the stopped reason, container exit code, and CloudWatch stream. Verify task role permissions, subnet internet access, S3 access, environment variables, command syntax, image tag, CPU architecture, and memory.

## API Returns 404

The resource may be configured but have no stored output. Confirm the corresponding dataset or model artifact exists in the configured production storage.
