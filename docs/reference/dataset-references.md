# Dataset References

Datasets use logical references with three colon-separated parts:

```text
layer:source:artifact
```

| Part | Values or meaning |
|---|---|
| `layer` | `bronze`, `silver`, or `gold` |
| `source` | Source, feature-set, dataset, or model name |
| `artifact` | `records`, `articles`, `features`, `datasets`, `embeddings`, or `forecasts` |

Examples:

```text
silver:eia_region:records
gold:eia_region_hourly:features
gold:hourly_load:datasets
gold:miso_hourly_load_sarimax:forecasts
```

For Bronze and Silver, `StoragePaths` resolves the general form to:

```text
data/{layer}/source={source}/artifact={artifact}/
```

Gold is grouped by artifact:

```text
data/gold/{artifact}/dataset={source}/
```

Names are normalized by trimming whitespace, replacing spaces with underscores, and replacing slashes, backslashes, and equals signs with hyphens.

Pipelines should pass logical references to storage methods and must not construct backend-specific local or S3 paths.
