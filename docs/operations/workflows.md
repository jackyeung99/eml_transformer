# Workflows

Workflows execute related stages in order and stop when a stage returns `status="failure"`. They reuse the same stage runners exposed as individual CLI commands.

## Available Workflows

| Workflow | Stages |
|---|---|
| `numeric` | ingest → standardize → build features → build datasets → train → forecast |
| `text` | ingest → standardize → scrape where configured → embed |
| `modeling` | build features → build datasets → train → forecast |
| `historical` | backfill → standardize → optional features and datasets |

## Commands

```bash
uv run eml_transformer workflow numeric \
  --config configs/dev.yaml
```

```bash
uv run eml_transformer workflow text \
  --source all \
  --config configs/dev.yaml
```

```bash
uv run eml_transformer workflow modeling \
  --force-train \
  --config configs/dev.yaml
```

```bash
uv run eml_transformer workflow historical \
  --source eia_region \
  --from-date 2025-01-01 \
  --to-date 2026-01-01 \
  --window-days 30 \
  --init-checkpoint \
  --build-downstream \
  --config configs/dev.yaml
```

When `all` is selected, only enabled definitions that support the stage run. An explicitly named disabled component may still run, with a warning, if it supports the requested stage.

The historical workflow does not train or forecast. Its optional downstream work ends after feature and dataset construction.

## Failure Behavior

Workflows stop between stages, not between individual items within one stage. All selected items in a stage are evaluated, and the next stage is skipped if any result has `status="failure"`.

## Related Documentation

- [CLI Reference](../guides/cli-reference.md)
- [Scheduling](scheduling.md)
- [Pipeline Documentation](../pipelines/ingestion.md)
