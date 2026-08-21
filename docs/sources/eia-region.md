# EIA Region

`eia_region` retrieves hourly EIA-930 balancing-authority operating data from `electricity/rto/region-data`.

| Code | Standard variable |
|---|---|
| `D` | `actual_load` |
| `DF` | `load_forecast` |
| `NG` | `net_generation` |
| `TI` | `total_interchange` |

The default respondent is MISO. Stable record identity combines source, respondent, measurement type, and period. Silver output is a `NumericRecord` with UTC `observed_at`, normalized value/unit, respondent as region, and EIA provenance metadata.

Configuration requires `EIA_API_KEY` through `api_key_env`. The source supports incremental ingestion, historical backfill, and standardization.
