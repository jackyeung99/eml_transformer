# Configuration Schema

The main YAML file is loaded into typed dataclasses before pipeline execution.

## Top-Level Sections

| Section | Type | Purpose |
|---|---|---|
| `storage` | mapping | Local or S3 backend |
| `sources` | mapping | Source definitions and stage eligibility |
| `embeddings` | mapping | Global embedding defaults |
| `features` | mapping | Feature definitions |
| `datasets` | mapping | Dataset definitions |
| `modeling` | mapping | Model definitions |

## Storage

`backend` defaults to `local`; `root` defaults to `data`. S3 additionally requires `bucket` and optionally accepts `prefix`, `region`, `profile`, and `endpoint_url`.

## Sources

Each source requires `config`, may set `enabled`, and contains a list of stages. Valid stages are `ingest`, `backfill`, `standardize`, `scrape`, and `embed`. The referenced YAML file is resolved relative to the main configuration directory and becomes `SourceDefinition.settings`.

## Features

Each feature requires `builder`, one string `input`, and `output`. `enabled` defaults to true and `settings` defaults to an empty mapping.

## Datasets

Each dataset requires `builder`, a nonempty mapping of named `inputs`, and `output`. `enabled` defaults to true and `settings` defaults to an empty mapping.

## Models

Each model requires `model_type`, training and forecast inputs, model and forecast outputs, and `target`. `features` must agree with `hyper_parameters.use_exogenous`. Optional `retrain_after_hours` must be a positive integer. Hyperparameters, training settings, and forecast settings must be mappings.

See [Configuration Guide](../guides/configuration.md) for examples and loader behavior.
