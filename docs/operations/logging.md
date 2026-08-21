# Logging

The CLI configures project-wide logging through `setup_logging()`. The default level is `INFO` and can be changed globally:

```bash
uv run eml_transformer --log-level DEBUG ingest --source eia_region
```

Pipeline logs use structured key-value messages containing component names, input/output references, record counts, elapsed time, and errors. `logger.exception()` includes a traceback for failures.

| Level | Use |
|---|---|
| `DEBUG` | Resolved paths, adapters, windows, and low-level progress |
| `INFO` | Stage starts, completions, counts, and timing |
| `WARNING` | Skips, missing optional input, disabled explicit selections |
| `ERROR` | Failed windows or operations |

Historical ingestion reduces repetitive log output while displaying its progress bar. AWS containers send stdout and stderr to their configured CloudWatch log group.

API keys are resolved at runtime and must never be logged. If a credential is missing, logs identify the environment-variable name, not its secret value.
