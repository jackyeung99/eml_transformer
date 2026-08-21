# Monitoring

Operational monitoring should cover four areas.

| Area | Checks |
|---|---|
| Data | Latest Bronze/Silver/Gold timestamps, row counts, failed records, checkpoint age |
| Models | Latest training time, version, validation metrics, diagnostics, retraining decision |
| Forecasts | Latest generation time, origin, horizon completeness, missing predictions |
| Service | ECS desired/running tasks, `/health`, API errors, latency, CloudWatch failures |

The current system relies primarily on CLI result tables, ECS task status, S3 inspection, the API health endpoint, and CloudWatch logs. Automated alarms and notifications are future improvements.

Recommended alerts include failed scheduled tasks, stale checkpoints, missing forecasts, unhealthy API tasks, and unusually high record-failure counts.

See [Logging](logging.md), [Scheduling](scheduling.md), and [Troubleshooting](troubleshooting.md).
