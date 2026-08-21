# Source Catalog

| Source | Type | Update mode | Backfill | Default status |
|---|---|---|---:|---|
| [EIA Region](eia-region.md) | Numeric | Incremental | Yes | Enabled |
| [EIA Interchange](eia-interchange.md) | Numeric | Incremental | Yes | Enabled |
| [MISO Notifications](miso-notifications.md) | Text | Snapshot | No | Enabled |
| [IEM AFOS](iem-afos.md) | Text | Incremental | Yes | Disabled |
| [GDELT](gdelt.md) | Text | Incremental | Yes | Disabled |
| [NewsAPI](newsapi.md) | Text | Incremental | Yes | Disabled |
| [Weather Alerts](weather-alerts.md) | Text | Snapshot | No | Disabled |

Enabled status varies by environment configuration. Use `uv run eml_transformer show sources --verbose` to inspect the selected configuration.
