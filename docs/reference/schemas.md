# Schemas

## BronzeRecord

| Field | Type | Description |
|---|---|---|
| `source` | `str` | Registered source name |
| `record_id` | `str` | Stable source-specific identifier |
| `published_at` | `datetime | None` | Source publication or observation time |
| `retrieved_at` | `datetime` | UTC retrieval time |
| `raw` | `dict[str, Any]` | Original source payload |

Bronze datetimes are serialized as UTC strings and reconstructed by `BronzeRecord.from_dict()`.

## TextRecord

| Field | Type | Required | Description |
|---|---|---:|---|
| `record_id` | `str` | Yes | Stable record identifier |
| `source` | `str` | Yes | Registered source |
| `source_type` | `str` | Yes | `text` |
| `title` | `str | None` | Yes | Document title when available |
| `text` | `str` | Yes | Standardized document text |
| `published_at` | `datetime | None` | Yes | Publication time |
| `retrieved_at` | `datetime` | Yes | Retrieval time |
| `url` | `str | None` | No | Source URL |
| `region` | `str | None` | No | Geographic or market region |
| `categories` | `list[str]` | No | Source or document categories |
| `dimensions` | `dict[str, str]` | No | Structured grouping dimensions |
| `metadata` | `dict[str, Any]` | No | Source-specific metadata |

## NumericRecord

| Field | Type | Required | Description |
|---|---|---:|---|
| `record_id` | `str` | Yes | Stable observation identifier |
| `source` | `str` | Yes | Registered source |
| `observed_at` | `datetime` | Yes | Canonical UTC observation time |
| `variable` | `str` | Yes | Standardized measurement name |
| `value` | `float` | Yes | Numeric measurement |
| `retrieved_at` | `datetime` | Yes | Retrieval time |
| `region` | `str | None` | No | Balancing authority or region |
| `unit` | `str | None` | No | Normalized unit |
| `dimensions` | `dict[str, str]` | No | Additional grouping dimensions |
| `metadata` | `dict[str, object]` | No | Source-specific provenance |

## Forecast Output

The active forecasting implementation writes a DataFrame containing `forecast_id`, model identity and version, model training time, UTC and Eastern generation/origin/target timestamps, integer horizon, and `predicted_value`.

Model metadata stores the fitted feature contract, target, hyperparameters, training settings, metrics, diagnostics, and training/validation periods. See [Modeling](../pipelines/modeling.md).
