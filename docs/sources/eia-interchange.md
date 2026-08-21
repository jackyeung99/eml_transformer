# EIA Interchange

`eia_interchange` retrieves hourly directional interchange from the EIA-930 `electricity/rto/interchange-data` route.

Its natural grain is observation period × originating balancing authority × receiving balancing authority. Configuration selects a balancing authority, optional neighbors, and `inbound`, `outbound`, or `both` directions.

Silver records use variable `interchange`, the configured balancing authority as region, and retain the from/to authority codes and names in dimensions and metadata. The source supports incremental ingestion, backfill, and standardization and requires `EIA_API_KEY`.
